"""
Async URL Validator for TriageBot

This module provides asynchronous functionality to validate URLs based on their type.
"""
import aiohttp
import asyncio
from typing import Dict, Any, List, Tuple
import logging
from functools import lru_cache
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AsyncURLValidator:
    """Asynchronously validates URLs based on their type."""
    
    def __init__(self, max_concurrent_requests: int = 10, timeout: int = 10):
        """Initialize the async URL validator.
        
        Args:
            max_concurrent_requests: Maximum number of concurrent HTTP requests
            timeout: Request timeout in seconds
        """
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        
    async def validate_urls(self, url_data: List[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
        """Validate multiple URLs concurrently.
        
        Args:
            url_data: List of tuples containing (url, url_type, ticket_number)
            
        Returns:
            List of validation results
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            tasks = [self._validate_single_url(session, url, url_type, ticket) 
                    for url, url_type, ticket in url_data]
            
            # Process in chunks to avoid overwhelming the server
            chunk_size = self.semaphore._value  # Get the semaphore value
            results = []
            
            for i in range(0, len(tasks), chunk_size):
                chunk = tasks[i:i + chunk_size]
                chunk_results = await asyncio.gather(*chunk, return_exceptions=True)
                
                # Process results
                for result in chunk_results:
                    if isinstance(result, Exception):
                        logger.error(f"Error during validation: {str(result)}")
                        continue
                    results.append(result)
                
                # Small delay between chunks
                if i + chunk_size < len(tasks):
                    await asyncio.sleep(0.1)
                    
            return results
    
    async def _validate_single_url(self, session: aiohttp.ClientSession, 
                                 url: str, url_type: str, ticket: str) -> Dict[str, Any]:
        """Validate a single URL with rate limiting."""
        async with self.semaphore:  # This limits concurrency
            try:
                if not url or not url.strip():
                    return self._create_result(ticket, False, 'Missing URL', 'URL is empty')
                    
                if not url.startswith(('http://', 'https://')):
                    return self._create_result(ticket, False, 'Invalid URL', 'URL must start with http:// or https://')
                
                # Route to the appropriate validation method
                if url_type and 'coveragev3' in url_type.lower():
                    return await self._validate_coveragev3_url(session, url, ticket)
                elif url_type and 'memberv3' in url_type.lower():
                    return await self._validate_memberv3_url(session, url, ticket)
                elif url_type and 'accums' in url_type.lower():
                    return await self._validate_accums_url(session, url, ticket)
                else:
                    return await self._validate_generic_url(session, url, ticket)
                    
            except Exception as e:
                logger.error(f"Error validating URL {url}: {str(e)}")
                return self._create_result(ticket, False, 'Validation Error', str(e))
    
    @staticmethod
    def _create_result(ticket: str, valid: bool, status: str, details: str, 
                      response_data: Any = None) -> Dict[str, Any]:
        """Create a standardized result dictionary."""
        return {
            'ticket': ticket,
            'valid': valid,
            'status': status,
            'details': details,
            'response_data': response_data
        }
    
    async def _validate_generic_url(self, session: aiohttp.ClientSession, 
                                  url: str, ticket: str) -> Dict[str, Any]:
        """Validate a generic URL."""
        try:
            async with session.get(url, allow_redirects=True) as response:
                if response.status == 200:
                    return self._create_result(
                        ticket, True, 'Active', 'URL is accessible (200 OK)')
                else:
                    return self._create_result(
                        ticket, False, f'HTTP {response.status}', 
                        f'Received status code: {response.status}')
                        
        except asyncio.TimeoutError:
            return self._create_result(
                ticket, False, 'Timeout', 'Request timed out')
        except Exception as e:
            return self._create_result(
                ticket, False, 'Connection Error', str(e))
    
    async def _validate_coveragev3_url(self, session: aiohttp.ClientSession, 
                                     url: str, ticket: str) -> Dict[str, Any]:
        """Validate a coveragev3 URL.
        
        Args:
            session: aiohttp ClientSession for making HTTP requests
            url: The URL to validate
            ticket: The ticket number for this validation
            
        Returns:
            Dict containing validation results with keys: valid, status, details
        """
        try:
            # Make the API call
            async with session.get(url) as response:
                if response.status != 200:
                    return self._create_result(
                        ticket, False,
                        f'HTTP {response.status}',
                        f'Received status code: {response.status}'
                    )
                
                # Check for error in response
                response_data = await response.json()
                if 'error' in str(response_data).lower():
                    return self._create_result(
                        ticket, False,
                        'failure from coverage API',
                        'Error found in API response',
                        response_data
                    )
                
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
                                start_date = datetime.strptime(
                                    coverage['coveragePeriod']['start'], '%Y-%m-%d'
                                ).date()
                                end_date = datetime.strptime(
                                    coverage['coveragePeriod']['end'], '%Y-%m-%d'
                                ).date()
                                
                                if start_date <= current_date <= end_date:
                                    active_coverage = True
                                    break
                            except (ValueError, KeyError, TypeError):
                                # If date parsing fails, skip this coverage item
                                continue
                
                status_parts.append('active coverage present' if active_coverage else 'active coverage missing')
                
                # Prepare final status
                final_status = ' | '.join(status_parts)
                
                return self._create_result(
                    ticket,
                    not mrid_missing and active_coverage,
                    final_status,
                    'Coverage validation completed',
                    response_data
                )
                
        except Exception as e:
            return self._create_result(
                ticket, False, 'Validation Error', str(e))
    
    async def _validate_memberv3_url(self, session: aiohttp.ClientSession, 
                                   url: str, ticket: str) -> Dict[str, Any]:
        """Validate a memberv3 URL.
        
        Args:
            session: aiohttp ClientSession for making HTTP requests
            url: The URL to validate
            ticket: The ticket number for this validation
            
        Returns:
            Dict containing validation results with keys: valid, status, details
        """
        try:
            # Make the API call
            async with session.get(url) as response:
                if response.status != 200:
                    return self._create_result(
                        ticket, False,
                        f'HTTP {response.status}',
                        f'Received status code: {response.status}'
                    )
                
                # Check for error in response
                response_data = await response.json()
                if 'error' in str(response_data).lower():
                    return self._create_result(
                        ticket, False,
                        'failure from member API',
                        'Error found in API response',
                        response_data
                    )
                
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
                
                return self._create_result(
                    ticket,
                    not mrid_missing,
                    final_status,
                    'Member validation completed',
                    response_data
                )
                
        except Exception as e:
            return self._create_result(
                ticket, False, 'Validation Error', str(e))
    
    async def _validate_accums_url(self, session: aiohttp.ClientSession, 
                                 url: str, ticket: str) -> Dict[str, Any]:
        """Validate an accums URL.
        
        Args:
            session: aiohttp ClientSession for making HTTP requests
            url: The URL to validate
            ticket: The ticket number for this validation
            
        Returns:
            Dict containing validation results with keys: valid, status, details
        """
        try:
            # Make the API call
            async with session.get(url) as response:
                if response.status != 200:
                    return self._create_result(
                        ticket, False,
                        f'HTTP {response.status}',
                        f'Received status code: {response.status}'
                    )
                
                # Parse the response
                response_data = await response.json()
                
                # Check 1: Check for errors in operationOutcome
                if 'operationOutcome' in response_data:
                    operation_outcome = response_data['operationOutcome']
                    if 'issue' in operation_outcome and isinstance(operation_outcome['issue'], list):
                        for issue in operation_outcome['issue']:
                            if 'details' in issue and isinstance(issue['details'], list):
                                for detail in issue['details']:
                                    if 'text' in detail and 'error' in str(detail['text']).lower():
                                        return self._create_result(
                                            ticket, False,
                                            'failure from accums API',
                                            f"Error in operation outcome: {detail['text']}",
                                            response_data
                                        )
                
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
                
                return self._create_result(
                    ticket,
                    amount_check_passed,
                    final_status,
                    'Accums validation completed',
                    response_data
                )
                
        except Exception as e:
            return self._create_result(
                ticket, False, 'Validation Error', str(e))
