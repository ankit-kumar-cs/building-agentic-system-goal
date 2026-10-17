# Test Plan

Feature: Test payment system

Date: 2026-10-17

Client: Beta | Project: Shop

## Description:

Test payment system

## Test Cases:

- **TC-1**: Enter valid card details, select product, click “Pay” -> Payment is processed successfully and order confirmation is displayed.  
- **TC-2**: Enter card details with insufficient funds, select product, click “Pay” -> Payment is declined and an error message “Insufficient funds” is shown.  
- **TC-3**: Enter expired card details, select product, click “Pay” -> Payment is declined and an error message “Card expired” is shown.  
- **TC-4**: Enter card details with incorrect CVV, select product, click “Pay” -> Payment is declined and an error message “Invalid CVV” is shown.

## Next Steps:

- Run the test cases and record results
- Move to deployment phase
