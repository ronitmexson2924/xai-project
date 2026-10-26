"""Deterministic Jinja2 template fallback for explanations.

Owner: Mit.
Guaranteed to execute locally without network access.
"""

import re

from jinja2 import BaseLoader, Environment

from app.contracts.explanation import StyleParams
from app.contracts.graph import ConceptCard

TEMPLATE_SOURCE = """
{% set example %}
```python
{{ card.worked_example | trim }}
```
{% endset %}
{% if style.length == 'short' %}
{% if style.example_first %}
For example:

{{ example }}

{{ card.definition }}
{% else %}
{{ card.definition }} For example:

{{ example }}
{% endif %}
{% elif style.length == 'medium' %}
{% if style.example_first %}
**Worked example**

{{ example }}

**Core idea**

{{ card.definition }} {{ card.key_idea }}
{% else %}
**Core idea**

{{ card.definition }} {{ card.key_idea }}

**Worked example**

{{ example }}
{% endif %}
{% else %}
{# Long length #}
{% if style.example_first %}
### A concrete example

{{ example }}

### The idea behind it

{{ card.definition }}

**Key idea:** {{ card.key_idea }}

**Common pitfall:** {{ card.pitfall }}
{% else %}
### The idea

{{ card.definition }}

**Key idea:** {{ card.key_idea }}

### A concrete example

{{ example }}

**Common pitfall:** {{ card.pitfall }}
{% endif %}
{% endif %}
""".strip()

_env = Environment(loader=BaseLoader(), autoescape=False)
_template = _env.from_string(TEMPLATE_SOURCE)


def render_template_fallback(card: ConceptCard, style: StyleParams) -> str:
    """Render a deterministic fallback explanation from concept card fields."""
    rendered = _template.render(card=card, style=style)
    # Collapse runs of blank lines to one: blank lines separate paragraphs and keep the worked
    # example's code fence on lines of its own, so they must not all be removed
    return re.sub(
        r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in rendered.split("\n"))
    ).strip()
