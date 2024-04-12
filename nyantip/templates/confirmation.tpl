{% set stats_url = "/r/{}/wiki/stats".format(config["reddit"]["subreddit"]) %}
{% if to_address: %}
{%   set explorer = config["coin"]["explorer"] %}
{%   set arrow_formatted = "[->]({}{})".format(explorer["transaction"], transaction_id) %}
{%   set destination_formatted = "[{}]({}{})".format(destination, explorer["address"], destination) %}
{% else: %}
{%   set arrow_formatted = "tipped" %}
{%   set destination_formatted = "u/{}".format(destination) %}
{% endif %}
{% if title|lower == "pending accept" %}
{%   set firstLinkText = "accept" %}
{%   set firstLinkUrl = "https://www.reddit.com/message/compose?to=pepetipbot&subject=accept&message=accept" %}
{%   set secondLinkText = "decline" %}
{%   set secondLinkUrl = "https://www.reddit.com/message/compose?to=pepetipbot&subject=decline&message=decline" %}
{% else: %}
{%   set firstLinkText = "wiki" %}
{%   set firstLinkUrl = "/r/{}/wiki/{}".format(config["reddit"]["subreddit"], "index") %}
{%   set secondLinkText = "stats" %}
{%   set secondLinkUrl = stats_url %}
{% endif %}
**^([{{ title }}]) u/{{ message.author }} {{ arrow_formatted }} {{ destination_formatted }} __{{ amount_formatted }}__** |[ {{ firstLinkText }} ]({{ firstLinkUrl }}) | [ {{ secondLinkText }} ]({{ secondLinkUrl }})|