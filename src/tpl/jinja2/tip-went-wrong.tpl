{% if to_address %}
{%   set destination_formatted = destination %}
{% else %}
{%   set destination_formatted = "u/{}".format(destination) %}
{% endif %}
Hey {{ message.author | replace('_', '\_') }}, something went wrong and your {{ action_name }} of __{{ amount_formatted }}__ to __{{ destination_formatted }}__ may not have been processed. My developer has been notified, and will look into the issue as soon as possible.

{% include 'footer.tpl' %}
