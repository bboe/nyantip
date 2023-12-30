{% set stats_url = "/r/{}/wiki/stats".format(config["reddit"]["subreddit"]) %}
{% if to_address: %}
{%   set explorer = config["coin"]["explorer"] %}
{%   set arrow_formatted = "[->]({}{})".format(explorer["transaction"], transaction_id) %}
{%   set destination_formatted = "[{}]({}{})".format(destination, explorer["address"], destination) %}
{% else: %}
{%   set arrow_formatted = "tipped" %}
{%   set destination_formatted = "u/{}".format(destination) %}
{% endif %}
**^([{{ title }}]) u/{{ message.author }} {{ arrow_formatted }} {{ destination_formatted }} __{{ amount_formatted }}__** |[ wiki ]({{ "/r/{}/wiki/{}".format(config["reddit"]["subreddit"], "index") }}) | [ stats ]({{ stats_url }})|
