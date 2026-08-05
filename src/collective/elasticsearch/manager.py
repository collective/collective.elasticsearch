@@
-        if client_choice in ("opensearch", "opensearch-py"):
-            if OpenSearch is None:
-                logger.error("OpenSearch requested but opensearch-py is not installed")
-                raise RuntimeError("opensearch-py is not available; install opensearch-py")
-            ClientClass = OpenSearch
+        if client_choice in ("opensearch", "opensearch-py"):
+            if OpenSearch is None:
+                logger.error("OpenSearch requested but opensearch-py is not installed")
+                raise RuntimeError(
+                    "opensearch-py is not available; install opensearch-py"
+                )
+            ClientClass = OpenSearch
@@
-            try:
-                if not getattr(client, "ping", lambda: True)():
-                    logger.warning("New search client ping() returned False")
-            except Exception:
-                logger.exception("Error pinging newly created search client (continuing)")
+            try:
+                if not getattr(client, "ping", lambda: True)():
+                    logger.warning("New search client ping() returned False")
+            except Exception:
+                logger.exception(
+                    "Error pinging newly created search client (continuing)"
+                )
