from __future__ import annotations

from reindex_server.database import Database
from reindex_server.domain import Collection, SearchHit, SearchOptions, SearchUnit


class ParadeDBSearch:
    """BM25, pgvector, and weighted-RRF retrieval backed by ParadeDB."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def search(
        self,
        collection: Collection,
        options: SearchOptions,
        query_embedding: list[float] | None,
    ) -> list[SearchHit]:
        if options.mode == "lexical":
            rows = self._lexical(collection, options)
        elif options.mode == "semantic":
            rows = self._semantic(
                collection, options, _require_embedding(query_embedding)
            )
        else:
            rows = self._hybrid(
                collection, options, _require_embedding(query_embedding)
            )
        return [_hit(row) for row in rows]

    def grep(
        self,
        collection: Collection,
        pattern: str,
        limit: int,
        regex: bool,
        case_sensitive: bool,
    ) -> list[SearchHit]:
        if regex:
            predicate = (
                "u.original_text ~ %s" if case_sensitive else "u.original_text ~* %s"
            )
        elif case_sensitive:
            predicate = "position(%s in u.original_text) > 0"
        else:
            predicate = "position(lower(%s) in lower(u.original_text)) > 0"
        sql = f"""
            SELECT u.*, 1.0::float8 AS score, NULL::float8 AS bm25_score,
                   NULL::float8 AS semantic_score, NULL::bigint AS lexical_rank,
                   NULL::bigint AS semantic_rank
            FROM search_units u
            WHERE u.revision_id = %s AND {predicate}
            ORDER BY u.node_id, u.ordinal, u.id
            LIMIT %s
        """
        return [
            _hit(row, "grep")
            for row in self._execute(sql, (collection.active_revision, pattern, limit))
        ]

    def _lexical(self, collection: Collection, options: SearchOptions) -> list[dict]:
        filters, filter_params = _filters("u", collection, options)
        sql = f"""
            WITH scored AS MATERIALIZED (
              SELECT u.*, pdb.score(u.id)::float8 AS bm25_score
              FROM search_units u
              WHERE {filters}
                AND (
                  u.title ||| %s::text::pdb.boost(4)
                  OR u.description ||| %s::text::pdb.boost(2)
                  OR u.original_text ||| %s::text
                )
              ORDER BY pdb.score(u.id) DESC, u.id
              LIMIT %s
            )
            SELECT scored.*, bm25_score AS score, NULL::float8 AS semantic_score,
                   row_number() OVER (ORDER BY bm25_score DESC, id) AS lexical_rank,
                   NULL::bigint AS semantic_rank
            FROM scored
            ORDER BY bm25_score DESC, id
        """
        params = (
            *filter_params,
            options.query,
            options.query,
            options.query,
            options.candidate_limit,
        )
        return self._execute(sql, params)

    def _semantic(
        self,
        collection: Collection,
        options: SearchOptions,
        embedding: list[float],
    ) -> list[dict]:
        filters, filter_params = _filters("u", collection, options)
        threshold = ""
        threshold_params: tuple = ()
        if options.semantic_threshold is not None:
            threshold = "AND 1 - (e.embedding <=> %s::vector) >= %s"
            threshold_params = (embedding, options.semantic_threshold)
        sql = f"""
            WITH scored AS MATERIALIZED (
              SELECT u.*, (1 - (e.embedding <=> %s::vector))::float8 AS semantic_score
              FROM search_units u
              JOIN unit_embeddings e ON e.unit_id = u.id
              WHERE {filters} AND e.profile_id = %s {threshold}
              ORDER BY e.embedding <=> %s::vector, u.id
              LIMIT %s
            )
            SELECT scored.*, semantic_score AS score, NULL::float8 AS bm25_score,
                   NULL::bigint AS lexical_rank,
                   row_number() OVER (ORDER BY semantic_score DESC, id) AS semantic_rank
            FROM scored
            ORDER BY semantic_score DESC, id
        """
        params = (
            embedding,
            *filter_params,
            collection.embedding_profile,
            *threshold_params,
            embedding,
            options.candidate_limit,
        )
        return self._execute(sql, params)

    def _hybrid(
        self,
        collection: Collection,
        options: SearchOptions,
        embedding: list[float],
    ) -> list[dict]:
        filters, filter_params = _filters("u", collection, options)
        semantic_filter = ""
        semantic_filter_params: tuple = ()
        if options.semantic_threshold is not None:
            semantic_filter = "AND 1 - (e.embedding <=> %s::vector) >= %s"
            semantic_filter_params = (embedding, options.semantic_threshold)
        sql = f"""
            WITH lexical_scored AS MATERIALIZED (
              SELECT u.id, pdb.score(u.id)::float8 AS bm25_score
              FROM search_units u
              WHERE {filters}
                AND (
                  u.title ||| %s::text::pdb.boost(4)
                  OR u.description ||| %s::text::pdb.boost(2)
                  OR u.original_text ||| %s::text
                )
              ORDER BY pdb.score(u.id) DESC, u.id
              LIMIT %s
            ),
            lexical AS (
              SELECT *, row_number() OVER (ORDER BY bm25_score DESC, id) AS lexical_rank
              FROM lexical_scored
            ),
            semantic_scored AS MATERIALIZED (
              SELECT u.id, (1 - (e.embedding <=> %s::vector))::float8 AS semantic_score
              FROM search_units u
              JOIN unit_embeddings e ON e.unit_id = u.id
              WHERE {filters} AND e.profile_id = %s {semantic_filter}
              ORDER BY e.embedding <=> %s::vector, u.id
              LIMIT %s
            ),
            semantic AS (
              SELECT *, row_number() OVER (ORDER BY semantic_score DESC, id) AS semantic_rank
              FROM semantic_scored
            ),
            fused AS (
              SELECT coalesce(lexical.id, semantic.id) AS id,
                     lexical.bm25_score, semantic.semantic_score,
                     lexical.lexical_rank, semantic.semantic_rank,
                     (CASE WHEN lexical.lexical_rank IS NULL THEN 0 ELSE
                        %s::float8 / (%s + lexical.lexical_rank) END
                      + CASE WHEN semantic.semantic_rank IS NULL THEN 0 ELSE
                        %s::float8 / (%s + semantic.semantic_rank) END)::float8 AS score
              FROM lexical FULL OUTER JOIN semantic USING (id)
            )
            SELECT u.*, fused.score, fused.bm25_score, fused.semantic_score,
                   fused.lexical_rank, fused.semantic_rank
            FROM fused JOIN search_units u USING (id)
            ORDER BY fused.score DESC, u.id
            LIMIT %s
        """
        params = (
            *filter_params,
            options.query,
            options.query,
            options.query,
            options.candidate_limit,
            embedding,
            *filter_params,
            collection.embedding_profile,
            *semantic_filter_params,
            embedding,
            options.candidate_limit,
            options.lexical_weight,
            options.rrf_k,
            options.semantic_weight,
            options.rrf_k,
            options.candidate_limit * 2,
        )
        return self._execute(sql, params)

    def _execute(self, sql: str, params: tuple) -> list[dict]:
        with self.database.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '2s'")
            cursor.execute(sql, params)
            return cursor.fetchall()


def _filters(
    alias: str, collection: Collection, options: SearchOptions
) -> tuple[str, tuple]:
    clauses = [f"{alias}.revision_id = %s"]
    params: list = [collection.active_revision]
    if options.node_ids:
        clauses.append(f"{alias}.node_id = ANY(%s::uuid[])")
        params.append(list(options.node_ids))
    if options.kinds:
        clauses.append(f"{alias}.kind = ANY(%s::text[])")
        params.append(list(options.kinds))
    if options.path_prefix:
        clauses.append(f"starts_with({alias}.path, %s)")
        params.append(options.path_prefix)
    return " AND ".join(clauses), tuple(params)


def _require_embedding(value: list[float] | None) -> list[float]:
    if value is None:
        raise RuntimeError("semantic and hybrid search require query embeddings")
    return value


def _hit(row: dict, forced_channel: str | None = None) -> SearchHit:
    ranks = {
        channel: int(row[key])
        for channel, key in (("lexical", "lexical_rank"), ("semantic", "semantic_rank"))
        if row.get(key) is not None
    }
    channels = (forced_channel,) if forced_channel else tuple(ranks)
    return SearchHit(
        unit=_unit(row),
        score=float(row["score"]),
        channels=channels,
        ranks=ranks,
        bm25_score=float(row["bm25_score"])
        if row.get("bm25_score") is not None
        else None,
        semantic_score=float(row["semantic_score"])
        if row.get("semantic_score") is not None
        else None,
    )


def _unit(row: dict) -> SearchUnit:
    return SearchUnit(
        id=row["unit_id"],
        node_id=str(row["node_id"]),
        contextual_text=row["contextual_text"],
        original_text=row["original_text"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        ordinal=row["ordinal"],
        row=row["row_number"],
        locator=row["locator"],
    )
