#!/usr/bin/env bash

# Настройка окружения для запуска инструментов Defects4J.
export JAVA_HOME="/opt/homebrew/opt/openjdk@11"
export PATH="$HOME/perl5/bin:$JAVA_HOME/bin:/Users/m.rudenko/mpr/project/defects4j/framework/bin:$PATH"
export PERL5LIB="$HOME/perl5/lib/perl5"
export D4J_HOME="/Users/m.rudenko/mpr/project/defects4j"
export TZ="America/Los_Angeles"

echo "Defects4J environment configured (JAVA_HOME=$JAVA_HOME)."
