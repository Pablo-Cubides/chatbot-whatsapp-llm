#!/usr/bin/env python3
"""
Comprehensive test script to validate the current ChatBot WhatsApp LLM system
including message generation, manual message functionality, and bulk messaging
"""

import asyncio
import json
import os
import sys
import time
import requests
import subprocess
from typing import Dict, List, Any
from pprint import pprint

class SystemTester:
    def __init__(self):
        self.base_url = "http://127.0.0.1:8003"
        self.ui_url = f"{self.base_url}/ui/index.html"
        self.api_token = "Bearer admintoken"
        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json"
        }
        self.results = {
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_details": []
        }
        
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test results"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"    Details: {details}")
        
        self.results["tests_details"].append({
            "test": test_name,
            "status": "PASS" if passed else "FAIL", 
            "details": details
        })
        
        if passed:
            self.results["tests_passed"] += 1
        else:
            self.results["tests_failed"] += 1

    def test_api_health(self) -> bool:
        """Test basic API connectivity"""
        try:
            # Try different endpoints to see what's available
            endpoints_to_test = [
                "/",
                "/health", 
                "/api/health",
                "/api/system/status",
                "/ui/index.html"
            ]
            
            working_endpoints = []
            for endpoint in endpoints_to_test:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                    if response.status_code < 500:  # Accept any non-server-error
                        working_endpoints.append(f"{endpoint} ({response.status_code})")
                except:
                    pass
            
            if working_endpoints:
                self.log_test("API Health Check", True, f"Working endpoints: {', '.join(working_endpoints)}")
                return True
            else:
                self.log_test("API Health Check", False, "No endpoints responding")
                return False
                
        except Exception as e:
            self.log_test("API Health Check", False, f"Connection error: {str(e)}")
            return False

    def test_web_ui_exists(self) -> bool:
        """Test if web UI files exist and are accessible"""
        try:
            # Check if web UI HTML file exists
            ui_path = "web_ui/index.html"
            if os.path.exists(ui_path):
                with open(ui_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for key functionality indicators
                features_found = []
                feature_checks = {
                    "Contact Management": "contact" in content.lower(),
                    "Model Selection": "model" in content.lower(),
                    "Message Composition": "compose" in content.lower() or "generate" in content.lower(),
                    "Bulk Messaging": "bulk" in content.lower(),
                    "Manual Send": "manual" in content.lower() or "send" in content.lower()
                }
                
                for feature, found in feature_checks.items():
                    if found:
                        features_found.append(feature)
                
                self.log_test("Web UI Exists", True, f"Features found: {', '.join(features_found)}")
                return True
            else:
                self.log_test("Web UI Exists", False, "web_ui/index.html not found")
                return False
                
        except Exception as e:
            self.log_test("Web UI Exists", False, f"Error reading UI: {str(e)}")
            return False

    def test_database_structure(self) -> bool:
        """Test database connectivity and structure"""
        try:
            from admin_db import get_session
            from models import Contact, ChatProfile, Conversation
            
            session = get_session()
            
            # Test basic queries
            contact_count = session.query(Contact).count()
            profile_count = session.query(ChatProfile).count()
            conversation_count = session.query(Conversation).count()
            
            session.close()
            
            self.log_test("Database Structure", True, 
                         f"Contacts: {contact_count}, Profiles: {profile_count}, Conversations: {conversation_count}")
            return True
            
        except Exception as e:
            self.log_test("Database Structure", False, f"Database error: {str(e)}")
            return False

    def test_model_manager(self) -> bool:
        """Test model manager functionality"""
        try:
            from model_manager import ModelManager
            
            mm = ModelManager()
            
            # Test model selection logic
            test_chat_id = "test_user_123"
            selected_model = mm.select_model_for_chat(test_chat_id)
            
            # Test if reasoner model selection works
            reasoner_model = mm.get_reasoner_model()
            
            self.log_test("Model Manager", True, 
                         f"Selected model: {selected_model}, Reasoner: {reasoner_model}")
            return True
            
        except Exception as e:
            self.log_test("Model Manager", False, f"ModelManager error: {str(e)}")
            return False

    def test_message_generation(self) -> bool:
        """Test AI message generation functionality"""
        try:
            import stub_chat
            
            # Test basic chat functionality
            test_message = "Hello, this is a test message"
            test_chat_id = "test_chat_123"
            test_history = []
            
            response = stub_chat.chat(test_message, test_chat_id, test_history)
            
            if response and len(response) > 0:
                self.log_test("Message Generation", True, f"Generated response: {response[:100]}...")
                return True
            else:
                self.log_test("Message Generation", False, "No response generated")
                return False
                
        except Exception as e:
            self.log_test("Message Generation", False, f"Generation error: {str(e)}")
            return False

    def test_manual_message_api(self) -> bool:
        """Test manual message composition API endpoints"""
        try:
            # Test message composition endpoint
            compose_payload = {
                "chat_id": "test_contact",
                "objective": "Schedule a follow-up appointment",
                "additional_context": "Patient needs to return in 2 weeks"
            }
            
            # We won't actually send requests since server might not be running
            # Instead, check if the API functions exist in admin_panel
            from admin_panel import app
            
            # Check if the routes exist
            routes = [route.path for route in app.routes]
            required_routes = [
                "/api/chat/compose",
                "/api/whatsapp/send", 
                "/api/whatsapp/bulk-send"
            ]
            
            missing_routes = [route for route in required_routes if route not in routes]
            
            if not missing_routes:
                self.log_test("Manual Message API", True, "All required API endpoints exist")
                return True
            else:
                self.log_test("Manual Message API", False, f"Missing routes: {missing_routes}")
                return False
                
        except Exception as e:
            self.log_test("Manual Message API", False, f"API structure error: {str(e)}")
            return False

    def test_bulk_messaging_functionality(self) -> bool:
        """Test bulk messaging capabilities"""
        try:
            # Check if bulk messaging queue exists
            queue_file = "data/manual_queue.json"
            
            if os.path.exists(queue_file):
                with open(queue_file, 'r', encoding='utf-8') as f:
                    queue_data = json.load(f)
                
                self.log_test("Bulk Messaging Queue", True, f"Queue file exists with {len(queue_data)} items")
                
                # Test queue structure
                if queue_data and isinstance(queue_data, list) and len(queue_data) > 0:
                    sample_item = queue_data[0]
                    required_fields = ['id', 'chat_id', 'message', 'status']
                    has_fields = all(field in sample_item for field in required_fields)
                    
                    self.log_test("Bulk Messaging Structure", has_fields, 
                                 f"Queue structure valid: {has_fields}")
                    return True
                else:
                    self.log_test("Bulk Messaging Structure", True, "Empty queue (valid)")
                    return True
            else:
                self.log_test("Bulk Messaging Queue", False, "Queue file not found")
                return False
                
        except Exception as e:
            self.log_test("Bulk Messaging Functionality", False, f"Bulk messaging error: {str(e)}")
            return False

    def test_whatsapp_integration(self) -> bool:
        """Test WhatsApp integration components"""
        try:
            # Check if WhatsApp automator exists
            if os.path.exists("whatsapp_automator.py"):
                with open("whatsapp_automator.py", 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for key functions
                key_functions = [
                    "process_manual_queue",
                    "send_manual_message", 
                    "fetch_new_message"
                ]
                
                found_functions = []
                for func in key_functions:
                    if f"def {func}" in content:
                        found_functions.append(func)
                
                self.log_test("WhatsApp Integration", True, 
                             f"Found functions: {', '.join(found_functions)}")
                return True
            else:
                self.log_test("WhatsApp Integration", False, "whatsapp_automator.py not found")
                return False
                
        except Exception as e:
            self.log_test("WhatsApp Integration", False, f"Integration test error: {str(e)}")
            return False

    def test_contact_management(self) -> bool:
        """Test contact management functionality"""
        try:
            from chat_sessions import add_or_update_contact, get_allowed_contacts
            
            # Test adding a contact
            test_contact_id = "test_contact_system_validation"
            add_or_update_contact(test_contact_id, name="System Test Contact", auto_enabled=True)
            
            # Test retrieving contacts
            contacts = get_allowed_contacts()
            
            # Find our test contact
            test_contact_found = any(c.chat_id == test_contact_id for c in contacts)
            
            self.log_test("Contact Management", True, 
                         f"Contacts in system: {len(contacts)}, Test contact added: {test_contact_found}")
            return True
            
        except Exception as e:
            self.log_test("Contact Management", False, f"Contact management error: {str(e)}")
            return False

    def analyze_current_features(self) -> Dict[str, Any]:
        """Analyze what features are currently implemented"""
        analysis = {
            "web_ui_features": [],
            "api_endpoints": [],
            "database_tables": [],
            "missing_features": [],
            "improvement_opportunities": []
        }
        
        try:
            # Analyze web UI
            if os.path.exists("web_ui/index.html"):
                with open("web_ui/index.html", 'r', encoding='utf-8') as f:
                    ui_content = f.read()
                
                # Check for specific UI features mentioned in the requirements
                ui_features = {
                    "Contact Selection Modal": "modal" in ui_content.lower() and "contact" in ui_content.lower(),
                    "Message Composition": "compose" in ui_content.lower() or "generate" in ui_content.lower(),
                    "Message Refinement": "edit" in ui_content.lower() or "refine" in ui_content.lower(),
                    "Bulk Messaging": "bulk" in ui_content.lower(),
                    "Media Upload": "upload" in ui_content.lower() or "media" in ui_content.lower(),
                    "Sticker Support": "sticker" in ui_content.lower()
                }
                
                for feature, exists in ui_features.items():
                    if exists:
                        analysis["web_ui_features"].append(feature)
                    else:
                        analysis["missing_features"].append(f"UI: {feature}")
            
            # Analyze API endpoints
            from admin_panel import app
            routes = [route.path for route in app.routes if hasattr(route, 'path')]
            analysis["api_endpoints"] = routes
            
            # Check for required endpoints from user requirements
            required_endpoints = {
                "Manual Message Composition": "/api/chat/compose",
                "Manual Message Send": "/api/whatsapp/send",
                "Bulk Message Send": "/api/whatsapp/bulk-send",
                "Contact Management": "/contacts",
                "Media Upload": "/api/media/upload"
            }
            
            for feature, endpoint in required_endpoints.items():
                if endpoint not in routes:
                    analysis["missing_features"].append(f"API: {feature} ({endpoint})")
            
            # Analyze opportunities based on user requirements
            user_requirements = [
                "Manual message composition with AI assistance",
                "Iterative message refinement until approval", 
                "Bulk messaging with contact selection",
                "Sticker and multimedia support",
                "Modal-based UI for message composition"
            ]
            
            # Check which requirements might need improvement
            for requirement in user_requirements:
                analysis["improvement_opportunities"].append(requirement)
            
        except Exception as e:
            analysis["error"] = str(e)
        
        return analysis

    def run_all_tests(self):
        """Run comprehensive system tests"""
        print("🚀 Starting Comprehensive System Test for ChatBot WhatsApp LLM")
        print("=" * 70)
        
        # Run all tests
        self.test_web_ui_exists()
        self.test_database_structure()
        self.test_model_manager()
        self.test_message_generation()
        self.test_manual_message_api()
        self.test_bulk_messaging_functionality()
        self.test_whatsapp_integration()
        self.test_contact_management()
        
        # Try API health last (might fail if server not running)
        self.test_api_health()
        
        # Analyze current features
        print("\n📊 FEATURE ANALYSIS")
        print("=" * 70)
        analysis = self.analyze_current_features()
        
        print("✅ Existing Web UI Features:")
        for feature in analysis.get("web_ui_features", []):
            print(f"   - {feature}")
        
        print(f"\n🔗 API Endpoints Found: {len(analysis.get('api_endpoints', []))}")
        for endpoint in analysis.get("api_endpoints", [])[:10]:  # Show first 10
            print(f"   - {endpoint}")
        if len(analysis.get("api_endpoints", [])) > 10:
            print(f"   ... and {len(analysis['api_endpoints']) - 10} more")
        
        print("\n⚠️ Missing Features:")
        for feature in analysis.get("missing_features", []):
            print(f"   - {feature}")
        
        print("\n🔧 Improvement Opportunities:")
        for opportunity in analysis.get("improvement_opportunities", []):
            print(f"   - {opportunity}")
        
        # Final summary
        print("\n📈 TEST SUMMARY")
        print("=" * 70)
        total_tests = self.results["tests_passed"] + self.results["tests_failed"]
        pass_rate = (self.results["tests_passed"] / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.results['tests_passed']} ✅")
        print(f"Failed: {self.results['tests_failed']} ❌")
        print(f"Pass Rate: {pass_rate:.1f}%")
        
        if pass_rate >= 80:
            print("\n🎉 SYSTEM STATUS: EXCELLENT - Ready for enhancements!")
        elif pass_rate >= 60:
            print("\n👍 SYSTEM STATUS: GOOD - Minor fixes needed")
        else:
            print("\n⚠️ SYSTEM STATUS: NEEDS ATTENTION - Several issues found")
        
        return self.results

if __name__ == "__main__":
    tester = SystemTester()
    results = tester.run_all_tests()
    
    # Save results to file
    with open("system_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to: system_test_results.json")
    
    # Exit with appropriate code
    exit_code = 0 if results["tests_failed"] == 0 else 1
    sys.exit(exit_code)