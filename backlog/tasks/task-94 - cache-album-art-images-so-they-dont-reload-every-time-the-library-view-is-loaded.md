---
id: TASK-94
title: >-
  cache album art images so they don't reload every time the library view is
  loaded
status: To Do
assignee: []
created_date: '2026-04-08 13:37'
labels: []
milestone: m-26
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
There are a lot of requests to get album art every time the Library view is shown. These should be cached: album art is unlikely to change between view loads.  Album file updates can be the semaphore for cache invalidation.
<!-- SECTION:DESCRIPTION:END -->
