Hello u/{{ message.author }}, here are your last 75 transactions.

{{ "|".join(keys) }}
{{ "|".join([":---"] * (keys|length)) }}
{% for item in history %}
{{   "|".join(item) }}
{% endfor %}

{% include 'footer.tpl' %}
