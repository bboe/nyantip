{% set help_link = "[verify syntax](%s)" % ctb.conf["reddit"]["help"]["url"] %}
Sorry {{ user_from | replace('_', '\_') }}, I didn't understand your {{ what }}. Please {{ help_link }} and try again.

{% set user = user_from %}
{% include 'footer.tpl' %}
