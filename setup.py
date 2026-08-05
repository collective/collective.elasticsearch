---
*** Begin Patch
*** Update File: setup.py
@@
     extras_require={
@@
         "redis": [
             "redis",
             "rq",
             "requests",
             "cbor2",
         ],
+        "opensearch": [
+            "opensearch-py",
+        ],
     },
*** End Patch
