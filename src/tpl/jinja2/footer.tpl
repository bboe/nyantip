{% set user_bot = ctb.conf["reddit"]["auth"]["username"] %}
{% set compose_url = "https://www.reddit.com/message/compose?to=%s&subject=%s&message=%%2B%s" %}
{% set i_url = compose_url % (user_bot, "info", "info") %}
{% set h_url = compose_url % (user_bot, "history", "history") %}
{% set w_url = compose_url % (user_bot, "withdraw", "withdraw%20ADDRESS%20AMOUNT%20COIN_NAME") %}
{% set help_link = " ^[[help]](%s)" % ctb.conf["reddit"]["help"]["url"] %}
{% set contact_link = " ^[[contact]](%s)" % ctb.conf["reddit"]["contact"]["url"] %}
{% set stats_user_link = " **^[[your_stats]](%s_%s)**" % (ctb.conf["reddit"]["stats"]["url"], user) %}
{% set stats_global_link = " ^[[global_stats]](%s)" % ctb.conf["reddit"]["stats"]["url"] %}
*****

links ^(nyan)|&nbsp;
:---|:---
{% if a and a.msg and a.msg.permalink %}
^Source ^comment|^[[link]]({{ a.msg.permalink }})
{% elif source_link %}
^Source ^comment|^[[link]]({{ source_link }})
{% endif %}
^Quick ^commands|**^[+info]({{ i_url }})** ^[+history]({{ h_url }}) ^[+withdraw]({{ w_url }})
^Resources|{{ help_link }}{{ contact_link }}{{ stats_user_link }}{{ stats_global_link }}

{% include 'announcement.tpl' %}
