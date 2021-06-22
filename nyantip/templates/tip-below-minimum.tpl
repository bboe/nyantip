I'm sorry u/{{ message.author }}, your {{ action_name }} of __{{ amount_formatted }}__ is below the minimum of __{{ minimum_formatted }}__. I cannot process very small transactions because of network fee requirements.

If you really need to {{ action_name }}, try depositing some {{ config["coin"]["name"] }} to meet the minimum limit and then try again.

{% include 'footer.tpl' %}
