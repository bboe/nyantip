{% set bot = config["reddit"]["username"] %}
{% set subreddit = config["reddit"]["subreddit"] %}
{% set wiki_url = "/r/{}/wiki/{{}}".format(subreddit) %}
{% set compose_url = "/message/compose?to={}&subject={}&message={}" %}
{% set contact_format = " ^[[contact]](/message/compose/?to={})".format(bot) %}
{% set help_format = " ^[[help]]({})".format(wiki_url.format("index")) %}
{% set history_url = compose_url.format(bot, "history", "history") %}
{% set info_url = compose_url.format(bot, "info", "info") %}
{% set stats_global_format = " ^[[global_stats]]({})".format(wiki_url.format("stats")) %}
{% set stats_user_format = " **^[[your_stats]]({}_{})**".format(wiki_url.format("stats"), message.author) %}
{% set tip_url = compose_url.format(bot, "tip", config["tip_message_body_url_encoded"]) %}
{% set withdrawl_url = compose_url.format(bot, "withdraw", config["withdraw_message_body_url_encoded"]) %}
*****

links|&nbsp;
:---|:---
{% if message.context %}
^Source ^comment|^[[link]]({{ message.context }})
{% endif %}
^Quick ^commands|**^[info]({{ info_url }})** ^[history]({{ history_url }}) ^[tip]({{ tip_url }}) ^[withdraw]({{ withdrawl_url }})
^Resources|{{ help_format }}{{ contact_format }}{{ stats_user_format }}{{ stats_global_format }}

{% include 'announcement.tpl' %}
