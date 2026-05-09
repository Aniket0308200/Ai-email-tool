"""
Contacts Manager - Store and manage email contacts
"""
import json
import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACTS_FILE = os.path.join(BASE_DIR, "contacts.json")


class ContactsManager:
    """Manage saved email contacts"""
    
    def __init__(self):
        """Initialize contacts manager"""
        self.contacts = self._load_contacts()
    
    def _load_contacts(self) -> Dict[str, str]:
        """Load contacts from JSON file"""
        if os.path.exists(CONTACTS_FILE):
            try:
                with open(CONTACTS_FILE, "r") as f:
                    contacts = json.load(f)
                    logger.info(f"✅ Loaded {len(contacts)} contacts")
                    return contacts
            except Exception as e:
                logger.warning(f"Failed to load contacts: {e}")
        return {}
    
    def _save_contacts(self):
        """Save contacts to JSON file"""
        try:
            with open(CONTACTS_FILE, "w") as f:
                json.dump(self.contacts, f, indent=2)
            logger.info("✅ Contacts saved")
        except Exception as e:
            logger.error(f"Failed to save contacts: {e}")
    
    def add_contact(self, name: str, email: str) -> bool:
        """Add a new contact"""
        if not name or not email:
            logger.warning("Contact name and email are required")
            return False
        
        self.contacts[name] = email
        self._save_contacts()
        logger.info(f"✅ Contact added: {name} -> {email}")
        return True
    
    def remove_contact(self, name: str) -> bool:
        """Remove a contact"""
        if name in self.contacts:
            del self.contacts[name]
            self._save_contacts()
            logger.info(f"✅ Contact removed: {name}")
            return True
        logger.warning(f"Contact not found: {name}")
        return False
    
    def get_contact_email(self, name: str) -> Optional[str]:
        """Get email for a contact name"""
        return self.contacts.get(name)
    
    def get_all_contacts(self) -> Dict[str, str]:
        """Get all contacts"""
        return self.contacts.copy()
    
    def search_contacts(self, query: str) -> Dict[str, str]:
        """Search contacts by name or email"""
        query_lower = query.lower()
        return {
            name: email
            for name, email in self.contacts.items()
            if query_lower in name.lower() or query_lower in email.lower()
        }
    
    def contact_exists(self, name: str) -> bool:
        """Check if contact exists"""
        return name in self.contacts
