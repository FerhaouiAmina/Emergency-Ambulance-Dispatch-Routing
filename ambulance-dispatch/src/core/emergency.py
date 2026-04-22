from core.node import Node

class Emergency(Node):
    def __init__(self, node_id, x, y, severity=1):
        super().__init__(node_id, x, y, "emergency")
        self.severity = severity
