#!/bin/bash
export CATALINA_OPTS="-Xms512m -Xmx1024m -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/data/dump -Djava.awt.headless=true -Dfile.encoding=UTF-8 -Dpetclinic.config.location=file:/run/petclinic/data-access.properties"
