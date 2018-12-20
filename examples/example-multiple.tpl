{% for host in hosts -%}
  {% for neededservice in host.nagiosService -%}
    {% for service in services -%}
      {%- if service.cn.0 == neededservice %}
define service{
  host_name               {{ host.cn.0 }}
  service_description     {{ service.description.0 }}
  check_command           {{ service.command.0 }}
  max_check_attempts      3
  check_interval          5
  retry_interval          1
  check_period            {{ host.timePeriod.0 | default('24x7', true) }}
  notification_interval   30
  notification_period     {{ host.timePeriod.0 | default('24x7', true) }}
  notification_options    w,c,r,f
  contact_groups          nobody
}
      {%- endif %}
    {%- endfor %}
  {%- endfor %}
{%- endfor %}
