class Hospital:
    def __init__(self, id, node):
        self.id = id
        self.node = node

    def __repr__(self):
        return f"Hospital(id={self.id}, node={self.node})"
    