{% set user_from = action.u_from.name %}

Hello {{ user_from | replace('_', '\_') }}! Here's your account info.

coin|deposit address|balance
:---|:---|---:
{% set name_fmt = "%s (%s)" % (coin.conf["name"], coin.conf["unit"].upper()) %}
{% set address_fmt = "%s ^[[ex]](%s%s) ^[[qr]](%s%s)" % (address, coin.conf["explorer"]["url"], address, misc_conf["qr_service_url"], address) %}
{%   set coin_bal_fmt = "%.6f" % balance %}
__{{ name_fmt }}__|{{ address_fmt }}|__{{ coin_bal_fmt }}__
&nbsp;|&nbsp;|&nbsp;

Use addresses above to deposit coins into your account.

{% include 'footer.tpl' %}
