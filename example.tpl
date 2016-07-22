define host{
  host_name               __cn__
  alias                   __nagiosName__
  parents                 __nagiosParent__
  check_command           check-host-alive
  max_check_attempts      3
  normal_check_interval   5
  check_period            __timePeriod__
  contact_groups          nobody
  notification_interval   30
  notification_period     __timePeriod__
  notification_options    d,u,r,f
}
