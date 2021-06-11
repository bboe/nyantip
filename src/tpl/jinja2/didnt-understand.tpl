{% set help_link = "[verify syntax](%s)" % ctb.conf["reddit"]["help"] %}
Sorry {{ message.author | replace('_', '\_') }}, I didn't understand your {{ message_type }}. Please {{ help_link }} and try again.

{% include 'footer.tpl' %}
