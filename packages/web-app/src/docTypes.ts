export type CliParameter = {
  name: string;
  kind: "argument" | "option";
  type: string;
  required?: boolean;
  default?: string | number | boolean;
  flags?: string[];
  choices?: string[];
  minimum?: number;
  maximum?: number;
  description?: string;
};

export type CliCommand = {
  id: string;
  path: string[];
  summary: string;
  parameters: CliParameter[];
  constraints?: CliConstraint[];
  side_effects: string[];
  examples: string[];
  output_schema: { $ref: string };
};

export type CliConstraint = {
  kind: string;
  message: string;
};

export type CliContract = {
  spec: string;
  program: { name: string; summary: string; output: Record<string, string> };
  commands: CliCommand[];
};
