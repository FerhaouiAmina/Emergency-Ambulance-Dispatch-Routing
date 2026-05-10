class Hospital:
    def __init__(self, hid, node_id, name=""):
        self.id = hid
        self.node_id = node_id
        self.name = name

    def __repr__(self):
        return f"Hospital({self.id})"

>> ----------------------------------
# i suggest we add attribute to this code
"""
Hospital Implementation for Ambulance Dispatch
Author: M3 (Pair B)
Week 4 - Core Infrastructure
"""

from typing import Dict, Any, List


class Hospital:
    def __init__(self, id: int, x: float, y: float, name: str, capacity: int = 10):
        """
        Initialize a hospital
        
        Args:
            id: Unique hospital identifier
            x: X coordinate
            y: Y coordinate
            name: Hospital name
            capacity: Number of available beds/ambulance bays
        """
        self.id = id
        self.x = x
        self.y = y
        self.name = name
        self.capacity = capacity
        self.current_load = 0
        self.waiting_ambulances = []
    
    def admit_patient(self, ambulance_id: int) -> bool:
        """
        Admit a patient from an ambulance
        
        Args:
            ambulance_id: ID of the ambulance
            
        Returns:
            True if admitted, False if at capacity
        """
        if self.current_load < self.capacity:
            self.current_load += 1
            self.waiting_ambulances.append(ambulance_id)
            return True
        return False
    
    def discharge_patient(self) -> int:
        """
        Discharge a patient and free up capacity
        
        Returns:
            ID of the ambulance that can now leave
        """
        if self.waiting_ambulances:
            ambulance_id = self.waiting_ambulances.pop(0)
            self.current_load -= 1
            return ambulance_id
        return -1
    
    def get_availability(self) -> float:
        """Get availability ratio (0-1)"""
        return 1.0 - (self.current_load / self.capacity) if self.capacity > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert hospital to dictionary representation"""
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'name': self.name,
            'capacity': self.capacity,
            'current_load': self.current_load,
            'availability': self.get_availability()
        }
    
    def __str__(self) -> str:
        return f"Hospital({self.id}, '{self.name}', {self.current_load}/{self.capacity})"
    
    def __repr__(self) -> str:
        return self.__str__()


if __name__ == "__main__":
    # Test hospital functionality
    hospital = Hospital(1, 5.0, 5.0, "General Hospital", 5)
    
    print(f"Hospital: {hospital}")
    print(f"Availability: {hospital.get_availability():.2f}")
    
    # Admit patients
    for i in range(3):
        admitted = hospital.admit_patient(i)
        print(f"Admit ambulance {i}: {'Success' if admitted else 'Failed'}")
    
    print(f"Hospital after admissions: {hospital}")
    print(f"Availability: {hospital.get_availability():.2f}")
    
    # Discharge patients
    for i in range(2):
        ambulance_id = hospital.discharge_patient()
        print(f"Discharged ambulance {ambulance_id}")
    
    print(f"Hospital after discharges: {hospital}")
    print(f"Hospital dict: {hospital.to_dict()}")



<<------------------------------------
