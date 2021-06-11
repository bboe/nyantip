I'm sorry {{ message.author | replace('_', '\_') }}, u/{{ destination }} already has a pending tip from you. Please wait until it's accepted, declined, or expired.

{% include 'footer.tpl' %}
