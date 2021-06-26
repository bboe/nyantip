{% set user_from = a.u_from.name %}
{% set user_to = a.u_to.name %}
{% set coinval_fmt = "%s%.6g %s" % (ctb.conf["coin"]["symbol"], a.coinval, ctb.conf["coin"]["name"]) %}
Hey {{ user_from | replace('_', '\_') }}, you have successfully sent a __{{ coinval_fmt }}__ tip to /u/{{ user_to }} (nyan).
{% set user = user_from %}
{% include 'footer.tpl' %}
