{% set user_from = a.u_from.name %}
{% set user_to = a.u_to.name %}
{% if a.coinval: %}
{%   if a.coinval < 1.0 %}
{%     set coin_amount = ( a.coinval * 1000.0 ) %}
{%     set amount_prefix_short = "m" %}
{%     set amount_prefix_long = "milli" %}
{%   elif a.coinval >= 1000.0 %}
{%     set coin_amount = ( a.coinval / 1000.0 ) %}
{%     set amount_prefix_short = "k" %}
{%     set amount_prefix_long = "kilo" %}
{%   else %}
{%     set coin_amount = a.coinval %}
{%   endif %}
{% endif %}
{% set coinval_fmt = "%s%s%.6g %s%s" % (amount_prefix_short, ctb.conf["coins"][a.coin]["symbol"], coin_amount, amount_prefix_long, ctb.conf["coins"][a.coin]["name"]) %}
Hey {{ user_to | replace('_', '\_') }}, you have received a __{{ coinval_fmt }}__ tip from /u/{{ user_from }}.

Curious what a Nyancoin is and how you can use it? Check out /r/nyancoins :3

{% set user = user_to %}
{% include 'footer.tpl' %}
