{% set stats_url = "/r/{}/wiki/stats".format(config["reddit"]["subreddit"]) %}
{% if to_address: %}
{%   set explorer = config["coin"]["explorer"] %}
{%   set arrow_formatted = "[->]({}{})".format(explorer["transaction"], transaction_id) %}
{%   set destination_formatted = "[{}]({}{})".format(destination, explorer["address"], destination) %}
{% else: %}
{%   set arrow_formatted = "->" %}
{%   set destination_formatted = "u/{}^[[stats]]({}_{})".format(destination, stats_url, destination) %}
{% endif %}
__[{{ title }}]__

u/{{ message.author }}^[[stats]]({{ stats_url }}_{{ message.author }}) {{ arrow_formatted }} {{ destination_formatted }}

__{{ amount_formatted }}__

^[[help]]({{ "/r/{}/wiki/{}".format(config["reddit"]["subreddit"], "index") }})
^[[stats]]({{ stats_url }})
