from typing import List, Dict, Any
import json
import random

SYSTEM_INSTRUCTIONS = """
# Role
You are a market intelligence expert, specialized in the space sector and Earth Observation. You identify relevant key details in available news articles and provide a structurized output useful for data analysis.

# Objective
Given a news article, your objective is to identify key details regarding acquisitions, mergers, investments, IPO, partnerships, commercial contracts, etc., analyze the information and provide a structured output containing the information as specified by the structure proposed in [JSON structure](#JSON_structure).

# Rules
- You MUST provide only with data present in the article, estimates for numerical data such as contract size or investment amount are PROHIBITED
- You MUST follow the response template, the response will be validated by external audit
- You MUST NOT generate data that is not present within the article itself
- You MUST score the probability of topic relevancy separately for: 1) sector (i.e. if it is related to space and Earth Observation), 2) company (i.e. if it talks specifically about one of the companies provided), 3) event type (i.e. if it refers to the type of event provided). More details are provided in the [Relevance probability score](#Relevance_probability_score) section. 
- You CAN leave some entries as `null` or `[]` if the information is lacking or not relevant for the specific case

# Response template
The response provided shall be structured in the following manner:
1. Analysis of the news article and reasoning on the information contained and its relevancy
2. Divider on a new line with the following format: `{DIVIDER}`
3. Structured JSON containing the relevant information

Example:
\"\"\"
This article is relevant because of this and this and that...
They are talking about this and that...
{DIVIDER}
{{
    "company_relevancy_probability": 0.8,
    "event_relevancy_probability": 0.6,
    "sector_relevancy_probability": 1.0,
    ...
}}
\"\"\"

It is of the utmost importance that this template is followed at all times, the space **before** the divider is for you to reason on the article, the space **after** MUST follow exactly the JSON structure proposed in [JSON structure](#JSON_structure).

# Relevance probability score
The relevance probability score shall be a metric that measures the certainty of the relevancy of the specific article with respect to a certain topic or context. It shall represent a percentage value as a float number between 0.0 and 1.0 included.

Three relevancy probability scores need to be estimated:
- `sector_relevancy_probability`: if the article is referring to something connected to both the space sector and earth observation
- `company_relevancy_probability`: if the article is referring to something were one of the provided companies is involved
- `event_relevancy_probability`: if the article is referring to a type of event between the ones provided

If no company is provided, the `company_relevancy_probability` shall ALWAYS be equal to 1.0.
If no event type is provided, the `event_relevancy_probability` shall ALWAYS be equal to 1.0.

Meaning of some values:
- 0.0: it is certain that the article is irrelevant
- 0.25: it is probable that the article is irrelevant
- 0.5: it is unclear whether the article is relevant or not
- 0.75: it is probable that the article is relevant
- 1.0: it is certain that the article is relevant

# JSON schema
{{
    "company_relevancy_probability": {{
        "type": "float",
        "description": "a score from 0.0 to 1.0 representing the confidence in relevancy with respect to the set of companies specified in the relevant keywords"
    }},
    "event_relevancy_probability": {{
        "type": "float",
        "description": "a score from 0.0 to 1.0 representing the confidence in relevancy with respect to the set of event types specified in the relevant keywords"
    }},
    "sector_relevancy_probability": {{
        "type": "float",
        "description": "a score from 0.0 to 1.0 representing the confidence in relevancy with respect to the space and earth observation sector"
    }},
{SCHEMA}
}}

# Steps
1. READ the news article with attention
2. INTERNALIZE the required information provided in the JSON schema
3. ANALYSE the article, reasoning on the information useful to fill the JSON schema
4. EVALUATE the relevancy of the article for the requested topic(s) by proposing step-by-step the information in the article supporting or against its relevancy, and building a score from this evaluation as specified in the [Relevance probability score](#Relevance_probability_score) section.
5. ADD divider after completing the previous steps 
5. COMPOSE the required json using the requested schema

# Examples
{EXAMPLES}

# Relevant keywords:
- Companies: {COMPANIES}
- Event types: {EVENT_TYPES}
"""


DEFAULT_COMPANIES = ["Iceye", "Rheinmetall"]
DEFAULT_EVENT_TYPES = ["Partnership", "contract"]
DEFAULT_DIVIDER = "---"
DEFAULT_EXAMPLES = "TBD"
DEFAULT_SCHEMA = {
    "amount": {"type": "float", "description": "amount involved in the event", "min_value": 0},
}

class SystemPrompt():

    def __init__(self):
        self.prompt = SYSTEM_INSTRUCTIONS

    def configure(
            self,
            /,
            schema: Dict[str, Dict[str, Any]] = DEFAULT_SCHEMA,
            examples: str = DEFAULT_EXAMPLES,
            companies : List[str] = DEFAULT_COMPANIES,
            event_types: List[str] = DEFAULT_EVENT_TYPES,
            divider: str = DEFAULT_DIVIDER,
        ) -> str:
        schema_str = self.format_as_json_schema(schema)
        schema_example_str = self.format_as_json_example(schema)
        return self.prompt.format(
            SCHEMA=schema_str,
            SCHEMA_EXAMPLE=schema_example_str,
            EXAMPLES=examples,
            DIVIDER=divider,
            COMPANIES=self.format_as_list(companies),
            EVENT_TYPES=self.format_as_list(event_types),
        )
    
    @staticmethod
    def format_as_json_schema(schema: Dict[str, Dict[str, Any]]) -> str:
        lines: List[str] = []
        for key, props in schema.items():
            lines.append(f"{4 * " "}\"{key}\": {{")
            for subkey, subval in props.items():
                lines.append(f"{8 * " "}\"{subkey}\": {subval},")
            lines.append("    },")
        
        lines[-1].strip(",")

        return '\n'.join(lines)

    @staticmethod
    def format_as_json_example(schema: Dict[str, Dict[str, Any]]) -> str:
        if not schema:
            return ""
        example: Dict[str, Any] = {}
        for key, props in schema.items():
            t = str(props.get('type', 'string')).lower()
            if t in ('float', 'number'):
                if 'min_value' in props:
                    try:
                        example[key] = float(props['min_value'])
                    except Exception:
                        example[key] = 0.0
                elif 'max_value' in props:
                    try:
                        example[key] = float(props['max_value'])
                    except Exception:
                        example[key] = 0.0
                else:
                    example[key] = 0.0
            elif t in ('int', 'integer'):
                if 'min_value' in props:
                    try:
                        example[key] = int(props['min_value'])
                    except Exception:
                        example[key] = 0
                else:
                    example[key] = 0
            elif t in ('bool', 'boolean'):
                example[key] = False
            elif t in ('array', 'list'):
                example[key] = []
            elif t in ('object', 'dict'):
                example[key] = {}
            else:
                # string, date, datetime, etc.
                example[key] = props.get('example') if props.get('example') is not None else ""

        return json.dumps(example, indent=4)

    @staticmethod
    def format_as_list(list: List) -> str:
        if list is None:
            return "null"
        # if a single string was passed
        if isinstance(list, str):
            return list
        try:
            length = len(list)
        except Exception:
            return str(list)

        if length == 0:
            return "null"
        if length == 1:
            return str(list[0])
        # multiple elements -> show within brackets
        # represent elements as strings joined by comma+space
        return "[" + ", ".join(str(x) for x in list) + "]"
    
if __name__ == "__main__":
    prompt = SystemPrompt().configure()
    print(prompt)
