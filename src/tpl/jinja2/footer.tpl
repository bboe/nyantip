{% set compose_url = "https://www.reddit.com/message/compose?to=%s&subject=%s&message=%s" %}
{% set bot = ctb.conf["reddit"]["auth"]["username"] %}
{% set history_url = compose_url % (bot, "history", "history") %}
{% set info_url = compose_url % (bot, "info", "info") %}
{% set tip_url = compose_url % (bot, "tip", "tip%20u/USERNAME%20AMOUNT") %}
{% set withdrawl_url = compose_url % (bot, "withdraw", "withdraw%20ADDRESS%20AMOUNT") %}
{% set contact_link = " ^[[contact]](%s)" % ctb.conf["reddit"]["contact"] %}
{% set help_link = " ^[[help]](%s)" % ctb.conf["reddit"]["help"] %}
{% set stats_global_link = " ^[[global_stats]](%s)" % ctb.conf["reddit"]["stats"]["url"] %}
{% set stats_user_link = " **^[[your_stats]](%s_%s)**" % (ctb.conf["reddit"]["stats"]["url"], message.author) %}
*****

links ^(nyan)|&nbsp;
:---|:---
{% if message.context %}
^Source ^comment|^[[link]]({{ message.context }})
{% endif %}
^Quick ^commands|**^[info]({{ info_url }})** ^[history]({{ history_url }}) ^[tip]({{ tip_url }}) ^[withdraw]({{ withdrawl_url }})
^Resources|{{ help_link }}{{ contact_link }}{{ stats_user_link }}{{ stats_global_link }}

{% include 'announcement.tpl' %}
