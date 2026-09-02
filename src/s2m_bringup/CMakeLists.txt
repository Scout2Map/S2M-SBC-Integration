cmake_minimum_required(VERSION 3.8)
project(s2m_bringup)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  scripts/return_home_node.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME return_home
)

install(PROGRAMS
  scripts/sim_fault_injector.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME sim_fault_injector
)

install(PROGRAMS
  scripts/cmd_vel_safety_gate.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME cmd_vel_safety_gate
)

install(PROGRAMS
  scripts/drive_link_adapter.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME drive_link_adapter
)

install(FILES
  scripts/return_home_policy.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  config
  worlds
  DESTINATION share/${PROJECT_NAME}
)

install(FILES README.md DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(return_home_policy_test
    test/test_return_home_policy.py
  )
endif()

ament_package()
