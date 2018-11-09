{% for item in items %}
define host{
  host_name               {{ item.cn.0 }}
  alias                   {{ item.cn.0 }}
  parents                 {{ item.nagiosParent.0|default('', true) }}
  check_command           check-host-alive
  max_check_attempts      3
  normal_check_interval   5
  check_period            {{ item.timePeriod.0 | default('24x7', true) }}
  contact_groups          nobody
  notification_interval   30
  notification_period     {{ item.timePeriod.0 | default('24x7', true) }}
  notification_options    d,u,r,f
}
{% endfor %}
