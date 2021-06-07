{% set user_from = action.u_from.name %}

Hello {{ user_from | replace('_', '\_') }}! Here's your account info.

coin|deposit address|balance
:---|:---|---:
{% set name_fmt = "%s (%s)" % (coin.name, coin.unit.upper()) %}
{% set address_fmt = "%s ^[[ex]](%s%s) ^[[qr]](%s%s)" % (address, coin.explorer.address, address, misc_conf["qr_service_url"], address) %}
{%   set coin_bal_fmt = "%.6f" % i.balance %}
__{{ name_fmt }}__|{{ address_fmt }}|__{{ coin_bal_fmt }}__
&nbsp;|&nbsp;|&nbsp;

Use addresses above to deposit coins into your account.

{% include 'footer.tpl' %}
