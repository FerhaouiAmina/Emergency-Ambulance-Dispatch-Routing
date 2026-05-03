class Hospital:
    def __init__(self, hid, node_id, name=""):
        self.id = hid
        self.node_id = node_id
        self.name = name

    def __repr__(self):
        return f"Hospital({self.id})"