Feature: Detección de Matches
  Scenario: Match mutuo exitoso
    Given que "Juan" votó "Si" a "Juana"
    And que "Juana" votó "Si" a "Juan"
    When el motor de cruce procesa las respuestas
    Then se debe identificar un match entre "Juan" y "Juana"

  Scenario: Sin match por falta de reciprocidad
    Given que "Juan" votó "Si" a "Juana"
    And que "Juana" votó "No" a "Juan"
    When el motor de cruce procesa las respuestas
    Then no se debe identificar ningún match