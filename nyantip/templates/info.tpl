Hello u/{{ action.source }}! Here is your account info:

coin|deposit address|balance
:---|:---|---:
{% set name_format = "{} ({})".format(config["coin"]["name"], config["coin"]["unit"].upper()) %}
{% set address_format = "{} ^[[ex]]({}{}) ^[[qr]]({}{})".format(address, config["coin"]["explorer"]["address"], address, config["qr_url"], address) %}
{% set balance_format = "%.6f" % balance %}
__{{ name_format }}__|{{ address_format }}|__{{ balance_format }}__
&nbsp;|&nbsp;|&nbsp;

Use the address above to deposit coins into your account.

{% include 'footer.tpl' %}
