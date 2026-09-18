# Release validation

Run `mvn -f java/pom.xml clean install` followed by `mvn -f quarkus/pom.xml clean verify`.

The Java core unit tests and Python unit tests remain separate from HTTP integration tests. `NormalizeResourceIT` uses `@QuarkusIntegrationTest` and Maven Failsafe to execute the original API and HTML assertions against the packaged Quarkus JAR. `mvn test` alone does not run packaged integration tests; use `verify`.

This choice tests the same executable application shipped to users. The previous in-process `@QuarkusTest` bootstrap returned 404 for the REST resource despite the packaged JAR and container passing the real HTTP checks. No HTTP assertion was disabled or weakened: endpoint, engine, formats, context path and HTML checks are retained in the packaged integration phase.

Combined Windows/Linux workflows additionally start the actual frozen executable and verify both engines, mode switching, HTML selectors, logs and archive roots. Container workflows perform audit and normalization requests and verify context paths, non-root execution and real backend process shutdown.

Passing these checks does not guarantee pixel-identical document rendering across office suites. Test representative documents on copies before using a pre-release in production.
