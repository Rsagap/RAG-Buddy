---
source: https://portswigger.net/web-security/sql-injection/lab-retrieve-hidden-data
topic: sql-injection
type: LAB
---

- Web Security Academy
- SQL injection
- Lab

# Lab: SQL injection vulnerability in WHERE clause allowing retrieval of hidden data

This lab contains a SQL injection vulnerability in the product category filter. When the user selects a category, the application carries out a SQL query like the following:

To solve the lab, perform a SQL injection attack that causes the application to display one or more unreleased products.

#### Solution

- Use Burp Suite to intercept and modify the request that sets the product category filter.
- Modify the category parameter, giving it the value '+OR+1=1--
- Submit the request, and verify that the response now contains one or more unreleased products.

#### Community solutions

##### Intigriti

##### Rana Khalil

##### z3nsh3ll

##### Michael Sommer