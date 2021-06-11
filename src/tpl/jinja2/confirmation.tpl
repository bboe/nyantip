{% if to_address: %}
{%   set explorer = ctb.conf["coin"]["explorer"] %}
{%   set arrow_formatted = "[->]({}{})".format(explorer.transaction, transaction_id) %}
{%   set destination_formatted = "[{}]({}{})".format(destination, explorer["url"], destination) %}
{%   set stats_formatted = "" %}
{% else: %}
{%   set arrow_formatted = "->" %}
{%   set destination_formatted = "u/{}".format(destination) %}
{%   set stats_formatted = " ^^[[stats]]({}_{})".format(ctb.conf["reddit"]["stats"]["url"], destination) %}
{% endif %}
^__[{{ title }}]__

^u/{{ message.author }}^^[[stats]]({{ ctb.conf["reddit"]["stats"]["url"] }}_{{ message.author }}) ^{{ arrow_formatted }} ^{{ destination_formatted }}{{ stats_formatted }}

^__{{ amount_formatted }}__

^[[help]]({{ ctb.conf["reddit"]["help"] }})
^[[stats]]({{ ctb.conf["reddit"]["stats"]["url"] }})
