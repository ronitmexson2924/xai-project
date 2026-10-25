"""Deterministic Jinja2 template fallback for explanations.

Owner: Mit.
Guaranteed to execute locally without network access.
"""

from jinja2 import BaseLoader, Environment

from app.contracts.explanation import StyleParams
from app.contracts.graph import ConceptCard

TEMPLATE_SOURCE = """
{% if style.length == 'short' %}
{% if style.example_first %}
For example: {{ card.worked_example | trim }}. {{ card.definition }}
{% else %}
{{ card.definition }} For example: {{ card.worked_example | trim }}.
{% endif %}
{% elif style.length == 'medium' %}
{% if style.example_first %}
**Worked Example:**
{{ card.worked_example | trim }}

**Core Concept:**
{{ card.definition }}
{{ card.key_idea }}
{% else %}
**Core Concept:**
{{ card.definition }}
{{ card.key_idea }}

**Worked Example:**
{{ card.worked_example | trim }}
{% endif %}
{% else %}
{# Long length #}
{% if style.example_first %}
### Concrete Demonstration
{{ card.worked_example | trim }}

### Theoretical Foundation
{{ card.definition }}

**Key Idea:**
{{ card.key_idea }}

**Common Pitfall:**
{{ card.pitfall }}
{% else %}
### Theoretical Foundation
{{ card.definition }}

**Key Idea:**
{{ card.key_idea }}

### Concrete Demonstration
{{ card.worked_example | trim }}

**Common Pitfall:**
{{ card.pitfall }}
{% endif %}
{% endif %}
""".strip()

_env = Environment(loader=BaseLoader(), autoescape=False)
_template = _env.from_string(TEMPLATE_SOURCE)


def render_template_fallback(card: ConceptCard, style: StyleParams) -> str:
    """Render a deterministic fallback explanation from concept card fields."""
    rendered = _template.render(card=card, style=style)
    # Normalize excessive newlines
    lines = [line.rstrip() for line in rendered.split("\n")]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned
