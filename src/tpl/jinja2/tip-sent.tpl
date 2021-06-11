{% set coinval_fmt = "%s%.6g %s" % (ctb.conf["coin"]["symbol"], a.coinval, ctb.conf["coin"]["name"]) %}
Hey {{ message_author | replace('_', '\_') }}, you have successfully sent a __{{ coinval_fmt }}__ tip to u/{{ user_to }} (nyan).
{% set user = user_from %}
{% include 'footer.tpl' %}
