---
name: code-review
description: Review a file for bugs and unclear code. Use when asked to review, check or audit code.
---
1. Read the file with read_file. If no file was named, list_files and ask which one.
2. Look for, in this order: bugs (wrong logic, unhandled errors, edge cases),
   then security problems, then names or structure that are hard to follow.
3. Do not change the file. Reply with a short list, most serious first:
   `line N: what is wrong -> how to fix it`.
4. If nothing is wrong, say so in one line.
