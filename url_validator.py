"""
URL Validator for TriageBot

This module provides functionality to validate URLs based on their type.
"""
import requests
from typing import Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class URLValidator:
    """Validates URLs based on their type and updates status in Confluence."""
    
    @staticmethod
    def validate_url(url: str, url_type: str = None) -> Dict[str, Any]:
        """
        Validate a URL based on its type.
        
        Args:
            url: The URL to validate
            url_type: Type of URL to validate. Must be one of: 'coveragev3', 'memberv3', 'accums', or None
            
        Returns:
            Dict containing validation results with keys: valid, status, details
        """
        if not url or not url.strip():
            return {
                'valid': False,
                'status': 'Missing URL',
                'details': 'URL is empty'
            }
            
        # Common validation for all URL types
        if not url.startswith(('http://', 'https://')):
            return {
                'valid': False,
                'status': 'Invalid URL',
                'details': 'URL must start with http:// or https://'
            }
            
        # URL type specific validation
        if url_type and 'coveragev3' in url_type.lower():
            return URLValidator._validate_coveragev3_url(url)
        elif url_type and 'memberv3' in url_type.lower():
            return URLValidator._validate_memberv3_url(url)
        elif url_type and 'accums' in url_type.lower():
            return URLValidator._validate_accums_url(url)
        else:
            # Default validation for unspecified or empty types
            return URLValidator._validate_generic_url(url)
    
    @staticmethod
    def _validate_generic_url(url: str) -> Dict[str, Any]:
        """
        Default URL validation that checks if the URL is accessible.
        
        Args:
            url: The URL to validate
            
        Returns:
            Dict containing validation results
        """
        try:
            response = requests.get(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                return {
                    'valid': True,
                    'status': 'Active',
                    'details': 'URL is accessible (200 OK)'
                }
            else:
                return {
                    'valid': False,
                    'status': f'HTTP {response.status_code}',
                    'details': f'Received status code: {response.status_code}'
                }
                
        except requests.RequestException as e:
            return {
                'valid': False,
                'status': 'Connection Error',
                'details': str(e)
            }
    
    @staticmethod
    def _validate_coveragev3_url(url: str) -> Dict[str, Any]:
        """
        Validate a coveragev3 URL.
        
        Args:
            url: The URL to validate
            
        Returns:
            Dict containing validation results with keys: valid, status, details
        """
        from datetime import datetime
        import json
        
        try:
            # Make the API call
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Check for error in response
            response_data = response.json()
            if 'error' in str(response_data).lower():
                return {
                    'valid': False,
                    'status': 'failure from coverage API',
                    'details': 'Error found in API response'
                }
            
            status_parts = ['success calling coverage API']
            
            # Check 1: Verify masterRecordID exists in all coverage items
            mrid_missing = False
            if 'coverages' in response_data and isinstance(response_data['coverages'], list):
                for coverage in response_data['coverages']:
                    if 'businessIdentifier' not in coverage or 'masterRecordID' not in coverage['businessIdentifier']:
                        mrid_missing = True
                        break
            
            status_parts.append('mrid missing' if mrid_missing else 'mrid present')
            
            # Check 2: Check for active coverage period
            active_coverage = False
            current_date = datetime.now().date()
            
            if 'coverages' in response_data and isinstance(response_data['coverages'], list):
                for coverage in response_data['coverages']:
                    if 'coveragePeriod' in coverage:
                        try:
                            start_date = datetime.strptime(coverage['coveragePeriod']['start'], '%Y-%m-%d').date()
                            end_date = datetime.strptime(coverage['coveragePeriod']['end'], '%Y-%m-%d').date()
                            
                            if start_date <= current_date <= end_date:
                                active_coverage = True
                                break
                        except (ValueError, KeyError, TypeError):
                            # If date parsing fails, skip this coverage item
                            continue
            
            status_parts.append('active coverage present' if active_coverage else 'active coverage missing')
            
            # Prepare final status
            final_status = ' | '.join(status_parts)
            
            return {
                'valid': not mrid_missing and active_coverage,
                'status': final_status,
                'details': 'Coverage validation completed',
                'response_data': response_data  # Include full response for reference
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'valid': False,
                'status': 'API call failed',
                'details': str(e)
            }
        except json.JSONDecodeError:
            return {
                'valid': False,
                'status': 'Invalid JSON response',
                'details': 'The API did not return valid JSON'
            }
    
    @staticmethod
    def _validate_memberv3_url(url: str) -> Dict[str, Any]:
        """
        Validate a memberv3 URL.
        
        Args:
            url: The URL to validate
            
        Returns:
            Dict containing validation results with keys: valid, status, details
        """
        import json
        
        try:
            # Make the API call
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Check for error in response
            response_data = response.json()
            if 'error' in str(response_data).lower():
                return {
                    'valid': False,
                    'status': 'failure from member API',
                    'details': 'Error found in API response'
                }
            
            status_parts = ['success calling member API']
            
            # Check 1: Verify masterRecordID exists in all member items
            mrid_missing = False
            if 'members' in response_data and isinstance(response_data['members'], list):
                for member in response_data['members']:
                    if 'masterRecordID' not in member or not member['masterRecordID']:
                        mrid_missing = True
                        break
            
            status_parts.append('mrid missing' if mrid_missing else 'mrid present')
            
            # Prepare final status
            final_status = ' | '.join(status_parts)
            
            return {
                'valid': not mrid_missing,
                'status': final_status,
                'details': 'Member validation completed',
                'response_data': response_data  # Include full response for reference
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'valid': False,
                'status': 'API call failed',
                'details': str(e)
            }
        except json.JSONDecodeError:
            return {
                'valid': False,
                'status': 'Invalid JSON response',
                'details': 'The API did not return valid JSON'
            }
    
    @staticmethod
    def _validate_accums_url(url: str) -> Dict[str, Any]:
        """
        Validate an accums URL.
        
        Args:
            url: The URL to validate
            
        Returns:
            Dict containing validation results with keys: valid, status, details
        """
        import json
        
        try:
            # Make the API call
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse the response
            response_data = response.json()
            
            # Check 1: Check for errors in operationOutcome
            if 'operationOutcome' in response_data:
                operation_outcome = response_data['operationOutcome']
                if 'issue' in operation_outcome and isinstance(operation_outcome['issue'], list):
                    for issue in operation_outcome['issue']:
                        if 'details' in issue and isinstance(issue['details'], list):
                            for detail in issue['details']:
                                if 'text' in detail and 'error' in str(detail['text']).lower():
                                    return {
                                        'valid': False,
                                        'status': 'failure from accums API',
                                        'details': f"Error in operation outcome: {detail['text']}"
                                    }
            
            status_parts = ['success calling accums API']
            amount_check_passed = True
            
            # Check 2: Validate amounts in planBenefitsAndAccums
            if 'planBenefitsAndAccums' in response_data and isinstance(response_data['planBenefitsAndAccums'], list):
                for plan_benefit in response_data['planBenefitsAndAccums']:
                    # Check benefitMaximums
                    if ('planLevelBenefitInfo' in plan_benefit and 
                        'benefitMaximums' in plan_benefit['planLevelBenefitInfo'] and
                        'benefitMaximum' in plan_benefit['planLevelBenefitInfo']['benefitMaximums']):
                        
                        for benefit_max in plan_benefit['planLevelBenefitInfo']['benefitMaximums']['benefitMaximum']:
                            if 'remainingAmount' not in benefit_max or 'amount' not in benefit_max:
                                amount_check_passed = False
                                break
                    
                    # Check memberCostComponent
                    if (amount_check_passed and 
                        'planLevelBenefitInfo' in plan_benefit and 
                        'memberCost' in plan_benefit['planLevelBenefitInfo'] and
                        'memberCostComponent' in plan_benefit['planLevelBenefitInfo']['memberCost']):
                        
                        for cost_component in plan_benefit['planLevelBenefitInfo']['memberCost']['memberCostComponent']:
                            if 'remainingAmount' not in cost_component or 'amount' not in cost_component:
                                amount_check_passed = False
                                break
                    
                    if not amount_check_passed:
                        break
            
            status_parts.append('amount present in all segments' if amount_check_passed else 'amount missing in any or all segment')
            
            # Prepare final status
            final_status = ' | '.join(status_parts)
            
            return {
                'valid': amount_check_passed,
                'status': final_status,
                'details': 'Accums validation completed',
                'response_data': response_data  # Include full response for reference
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'valid': False,
                'status': 'API call failed',
                'details': str(e)
            }
        except json.JSONDecodeError:
            return {
                'valid': False,
                'status': 'Invalid JSON response',
                'details': 'The API did not return valid JSON'
            }
