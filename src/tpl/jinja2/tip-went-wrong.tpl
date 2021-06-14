{% if to_address %}
{%   set destination_formatted = " to __{}__".format(destination) %}
{% elif destination %}
{%   set destination_formatted = " to __u/{}__".format(destination) %}
{% else % }
{%   set destination_formatted = "" %}
{% endif %}
Hey {{ message.author | replace('_', '\_') }}, something went wrong and your {{ action_name }} of __{{ amount_formatted }}__{{ destination_formatted }} may not have been processed. My developer has been notified, and will look into the issue as soon as possible.

{% include 'footer.tpl' %}
