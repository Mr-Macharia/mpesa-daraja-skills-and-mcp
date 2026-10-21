# Sandbox setup and app creation

## Creating a Sandbox App

The **Mpesa Daraja platform** is a comprehensive set of programming tools, called **APIs** (Application Programming Interfaces), provided by Safaricom. These APIs allow businesses and developers to directly connect Mpesa services into their own applications. Before any real financial transactions can take place, it is essential to set up a secure and reliable testing environment.

This chapter focuses on the crucial first step: creating a **sandbox application** within the **Daraja Developer Portal**. A sandbox environment acts as a safe, isolated testing ground. It allows developers to simulate Mpesa transactions, test how their application integrates with the APIs, and fix any errors in their code without any risk of losing real money. This careful approach ensures that when an application is finally moved to the **production environment** (the live system), it will work correctly, securely, and exactly as intended, protecting both the business and its customers from potential errors and financial problems.

Creating a sandbox application is the first step to interacting with the Mpesa Daraja APIs in a controlled, risk-free setting. This process involves using the Daraja Developer Portal's interface, choosing the specific Mpesa APIs your application will use, and then generating unique **sandbox-specific credentials**. These credentials are required for your application to authenticate itself and simulate transactions. This section will guide you step-by-step through this essential setup, explaining the purpose and importance of each choice you make within the portal.

### 1. The Indispensable Role of the Sandbox Environment

Before we dive into the technical details of creating an application, it's vital to understand why a sandbox environment is not just convenient, but absolutely necessary for integrating financial technology.

A **sandbox environment** is a dedicated, isolated testing area that perfectly imitates the functions, data structures, and API behaviors of the live **production environment**. However, it operates using simulated data and has no real-world financial impact. In the context of Mpesa Daraja, this means that any transaction you start in the sandbox will not move actual money. Instead, it will simulate the flow of funds, update fake account balances, and trigger callback notifications as if real money were involved.

> 💡 **What is happening here:** The sandbox creates a safe, fake version of the Mpesa system. This allows developers to experiment and test their applications without any risk of real money being moved or lost, ensuring a secure learning and development process.

**Why the Sandbox is Crucial:**

*   **Prevention of Financial Loss:** This is the most immediate and obvious benefit. Any mistakes in your application's logic, API calls, or data formatting during development could lead to incorrect debits or credits in a live system. The sandbox completely removes this risk, allowing developers to make errors, learn from them, and correct them without any financial consequences.
*   **Safe Debugging and Iteration:** Developers can quickly test many different scenarios, unusual situations (edge cases), and error conditions. They can do this without worrying about corrupting live data or affecting real users. This speeds up the development cycle, making it possible to find and fix bugs much faster.
*   **API Familiarization:** The sandbox offers a practical learning platform to understand how each Mpesa API works. It shows what information the API expects as input and what results it provides as output. This hands-on experience is extremely valuable for developers who are new to the Daraja ecosystem.
*   **Performance and Scalability Testing (Limited):** While not a full-scale performance testing environment, the sandbox allows for initial checks of how an application interacts with the Mpesa APIs under various simulated workloads. This helps identify potential bottlenecks or slowdowns in the integration logic.
*   **Compliance and Security Prototyping:** Developers can test security measures, such as the correct handling of **API keys**, the encryption of sensitive data, and the secure configuration of **callback URLs**, all within a non-production setting. This helps ensure that security best practices are built into the application from the very beginning.

> 💡 **What is happening here:** The sandbox provides a safe space to prevent financial mistakes, quickly fix problems, learn how the Mpesa system works, and test security features. This prepares the application for real-world use.

**Distinction from Production Environment:**

The sandbox environment is fundamentally different from the **production environment**. The production environment is the live system where real financial transactions occur, directly affecting actual customer and business accounts. Key differences include:

*   **Data:** The sandbox uses simulated data, such as test phone numbers, fake transaction IDs, and artificial account balances. In contrast, the production environment uses real customer data and live financial records.
*   **Credentials:** Sandbox applications use specific **sandbox API keys** and **secrets**. Production applications require entirely separate **production API keys** and **secrets**, which are typically managed and secured with much stricter controls.
*   **Endpoints:** API requests made in the sandbox are sent to specific sandbox URLs (e.g., `https://sandbox.safaricom.co.ke/...`). Production requests, however, are directed to live production URLs (e.g., `https://api.safaricom.co.ke/...`).
*   **Impact:** Errors that occur in the sandbox have no real-world consequences. Errors in the production environment, however, can lead to financial losses, damage to a business's reputation, and disruptions to operations.

Understanding this distinction is extremely important. Developers must *never* use sandbox credentials or endpoints in a production application, nor production credentials or endpoints in a sandbox testing environment. Mixing these up is a common cause of integration failures and security vulnerabilities.

> 💡 **What is happening here:** It's crucial to understand that the sandbox and production environments are completely separate. Using the wrong credentials or URLs for each environment will cause errors and can lead to serious problems if done in the live system.

### 2. Accessing the Daraja Developer Portal

The journey to creating a sandbox application begins by accessing the **Daraja Developer Portal**. This portal serves as the central hub for managing all Mpesa integrations. Here, you can create applications, access API documentation, and monitor your usage.

**Prerequisites:** To get started, you must have a registered and verified Daraja developer account. This involves signing up with an email address, providing any necessary personal or business details, and completing any verification steps required by Safaricom.

**Login Process:**
1.  **Navigate to the official Daraja Developer Portal URL:** This is typically `https://developer.safaricom.co.ke/`.
2.  **Enter your credentials:** On the login page, type in your registered email address and password.
3.  **Access the dashboard:** After successfully authenticating, you will be redirected to the portal's main dashboard.

> 💡 **What is happening here:** You need a registered account to log into the Daraja Developer Portal, which is the central website for managing all your Mpesa integrations.

**Overview of the Portal Dashboard:**
The dashboard provides a high-level summary of your developer activities and available resources. Key sections you'll typically find include:
*   **My Apps:** This section displays a list of all applications (both sandbox and production) you have created under your account. It's where you'll create new applications and manage existing ones.
*   **API Documentation:** This provides links to comprehensive guides for all available Mpesa APIs. These documents detail request and response formats, required parameters, and possible error codes.
*   **Simulate:** These are tools that allow you to simulate various Mpesa transactions directly within the portal. This is useful for quick tests without needing to write any code.
*   **Support:** This section offers access to frequently asked questions (FAQs), developer forums, and contact information for technical support.
*   **Analytics/Reports:** (More commonly used for production applications) This provides metrics on your API usage, transaction volumes, and performance.

For the specific task of creating a sandbox application, the "My Apps" section will be your primary focus.

### 3. Understanding Applications in Daraja

In the Daraja ecosystem, an **Application** is a logical representation of your software system. This could be a mobile app, a web service, or an e-commerce platform that needs to interact with Mpesa APIs. Each application you create within the Daraja portal is assigned a unique set of credentials that identify and authenticate it when it makes API calls.

> 💡 **What is happening here:** An "Application" in Daraja is how your software is recognized by the Mpesa system. Each application gets unique keys to prove its identity when it tries to use Mpesa services.

**Why Applications are Necessary:**

*   **API Key Management:** Applications act as containers for your **API keys** and **secrets**. This centralized management simplifies the process of generating, revoking, and rotating these important credentials.
*   **Access Control and Permissions:** When you associate specific APIs with an application during its creation, the Daraja platform enforces the **principle of least privilege**. This fundamental security concept means that an application is only granted the absolute minimum permissions required to perform its intended function, thereby enhancing security.
*   **Usage Tracking and Billing:** Every API call made by an application is tracked. This allows Safaricom to monitor API usage, enforce **rate limits** (the maximum number of requests allowed in a given time), and, in a production context, potentially bill for services or provide usage analytics.
*   **Isolation of Concerns:** Different parts of a larger system or different development projects can have their own dedicated Daraja applications. This prevents credentials from being shared unnecessarily and simplifies troubleshooting. For example, an e-commerce platform might have one application for customer payments and another for vendor payouts, each with its own set of permissions and credentials.

> 💡 **What is happening here:** Applications help organize and secure your Mpesa integrations by managing API keys, controlling what services your software can access, tracking usage, and keeping different parts of your system separate.

**Relationship between an Application and API Keys/Secrets:**

When an application is created, the Daraja portal generates a unique pair of identifiers: a **Consumer Key** and a **Consumer Secret**. These two pieces of information are fundamental to the **OAuth 2.0 client credentials grant flow**, which Daraja uses for authentication. The **Consumer Key** identifies *who* is making the request (your application), and the **Consumer Secret** proves that *you are indeed who you claim to be* (it authenticates your application). Together, they are used to obtain a short-lived **Access Token**, which is then included in the header of all subsequent API requests to authorize them.

Other credentials, such as **Passkeys** for **Mpesa Express (STK Push)** or **Initiator Credentials** for B2C/B2B/Reversal APIs, are also linked to an application. These are specific to the particular Mpesa functionalities they enable and will be discussed in more detail as we proceed.

### 4. Step-by-Step Guide: Creating a Sandbox App

This section provides a detailed walkthrough of the process within the Daraja Developer Portal to create a functional sandbox application.

**4.1. Navigation to "My Apps" / "Create New App"**

1.  **Login to the Daraja Developer Portal:** As described previously, go to `https://developer.safaricom.co.ke/` and log in using your credentials.
2.  **Access "My Apps":** Once you're logged in, find the navigation menu. It's usually on the left side or at the top of the dashboard. Click on "My Apps."
3.  **Initiate New App Creation:** On the "My Apps" page, you'll see a list of any applications you've already created. To make a new one, look for a prominent button labeled "Add New App," "Create New App," or something similar. Click this button.

    *UI Walkthrough:* The "My Apps" page typically displays your applications in a table or list format. Each entry might show the app's name, when it was created, and its status (e.g., sandbox, production). The "Add New App" button is usually easy to spot, often colored differently or placed in a prominent location, such as the top-right corner of the application list.

> 💡 **What is happening here:** You start by logging into the Daraja Developer Portal, navigating to the "My Apps" section, and then clicking a button to begin creating a new application.

**4.2. App Name and Description**

After clicking "Add New App," a form will appear where you can define your new application. The first fields typically ask for an application name and a description.

*   **App Name:** This is a human-readable identifier for your application within the Daraja portal.
    *   *Input:* You can use a string of characters, usually alphanumeric, with some special characters allowed (like hyphens or underscores).
    *   *Purpose:* Its main purpose is to help you easily tell this application apart from others you might create. This is crucial for keeping things organized, especially if you manage many integrations.
    *   *Best Practices:*
        *   **Descriptive:** Choose a name that clearly indicates what the application does (e.g., "ECommerce_Sandbox_Payments," "Internal_Payroll_Test," "MobileApp_Dev_Env").
        *   **Unique:** While the portal might allow non-unique names, it's good practice to make them unique within your account to avoid confusion.
        *   **Environment-Specific:** Include "Sandbox" or "Dev" in the name to immediately identify its environment (e.g., "MyWebApp-Sandbox").

*   **Description:** This is an optional but highly recommended field where you can provide more context about the application.
    *   *Input:* A longer text string.
    *   *Purpose:* To explain more about the application's function, the project it belongs to, or any specific notes relevant to its use. This is particularly helpful when working in a team or revisiting an old project.
    *   *Example:* "Sandbox application for testing customer payments (STK Push, C2B) and refunds (B2C) for the new e-commerce platform v2.0."

> 💡 **What is happening here:** You give your new application a clear, descriptive name and an optional explanation. This helps you and your team understand its purpose and distinguish it from other applications.

**4.3. Selecting APIs**

This is a critical step where you define the specific Mpesa functionalities your application will be allowed to access. The Daraja portal typically presents a list of available APIs with checkboxes or toggle switches next to each. Selecting only the necessary APIs adheres to the **principle of least privilege**, a fundamental security concept that dictates a system or user should only be granted the minimum permissions required to perform its function.

Let's detail each core Mpesa API you might encounter and its purpose:

*   **Mpesa Express (STK Push):**
    *   *What it is:* Also known as **STK Push** (Sim Tool Kit Push), this API allows a business to initiate a payment request directly to a customer's mobile phone that is registered with Mpesa. The customer then receives a pop-up on their phone, asking them to enter their Mpesa PIN to complete the transaction.
    *   *How it works:* Your application sends a request to the Mpesa Express API. This request includes details like the customer's phone number, the amount to be paid, the business's **shortcode** (a unique number identifying the business), and a description of the transaction. Mpesa then sends a push notification to the customer's phone. Once the customer successfully enters their PIN, the transaction is completed, and a confirmation is sent to a **callback URL** you have configured.
    *   *Use Cases:* This is ideal for online shopping carts, paying utility bills, ride-hailing services, or any situation where a business wants to initiate a payment from a customer.

*   **C2B (Customer to Business):**
    *   *What it is:* This API makes it possible for customers to send payments from their Mpesa account directly to a business's Mpesa **Paybill** or **Till Number**. Unlike STK Push, the customer initiates the transaction themselves by going to the Mpesa menu on their phone, selecting "Lipa na Mpesa," and then choosing "Pay Bill" or "Buy Goods."
    *   *How it works:* The customer manually enters the business's Paybill/Till number, an account number (if required), and the amount. Mpesa then processes the payment. For businesses that want to receive real-time notifications about these payments, the C2B API provides a way to register a **Validation URL** (to accept or reject a transaction *before* it completes) and a **Confirmation URL** (to receive a notification *after* a transaction is successfully completed).
    *   *Use Cases:* This is commonly used by retail stores, supermarkets, schools, churches, and utility companies—essentially any business that receives payments initiated by the customer.

*   **B2C (Business to Customer):**
    *   *What it is:* This API allows a business to send funds from its Mpesa account to individual customer Mpesa accounts.
    *   *How it works:* Your application sends a request to the B2C API with details such as the customer's phone number, the amount, and a transaction description. The funds are then transferred from the business's Mpesa account to the customer's account. This API typically requires an **Initiator Username** and an encrypted **Security Credential** for authentication, as it involves money moving *out* of the business's account.
    *   *Use Cases:* This is used for salary payments, refunds, prize money disbursements, loan disbursements, and affiliate payouts.
    *   *Security Implications:* Because it involves disbursing funds, B2C transactions are highly sensitive. They require robust security measures, including strong authentication and often **IP whitelisting** (only allowing requests from specific, approved IP addresses) in a production environment.

*   **B2B (Business to Business):**
    *   *What it is:* This API facilitates payments from one business's Mpesa account to another business's Mpesa account. It is typically used for transfers between companies or payments to suppliers.
    *   *How it works:* Similar to B2C, your application sends a request containing the recipient business's shortcode, the amount, and other relevant details. It also requires an **Initiator Username** and **Security Credential**.
    *   *Use Cases:* This is used for supplier payments, transfers between different branches of a company, or payments to distributors and partners.

*   **Account Balance:**
    *   *What it is:* This API allows your application to check the current Mpesa balance of a specified business shortcode (either a Paybill or Till Number).
    *   *How it works:* Your application sends a request with the business shortcode. The API then returns the current available balance. This API also requires an **Initiator Username** and **Security Credential**.
    *   *Use Cases:* This is useful for monitoring a business's Mpesa account liquidity, reconciling financial records, or triggering alerts when balances fall below a certain threshold.

*   **Transaction Status:**
    *   *What it is:* This API allows your application to check the status of a specific Mpesa transaction (such as an STK Push, C2B, B2C, or B2B transaction) using its unique **transaction ID**.
    *   *How it works:* Your application sends a request with the transaction ID. The API then returns detailed information about the transaction, including its current status (e.g., completed, pending, failed). This API also requires an **Initiator Username** and **Security Credential**.
    *   *Use Cases:* This is crucial for reconciling transactions, providing customer support, handling delayed confirmations, and verifying if a payment was successful.

*   **Reversal:**
    *   *What it is:* This API enables a business to reverse a previously completed Mpesa transaction. This is typically used in situations involving erroneous payments or customer disputes.
    *   *How it works:* Your application sends a request with the original transaction ID and the amount to be reversed. The funds are then returned to the sender of the original transaction. This API also requires an **Initiator Username** and **Security Credential**.
    *   *Use Cases:* This is used for correcting mistaken payments or processing refunds for returned goods (if the original payment was C2B/STK Push).
    *   *Operational Considerations:* Reversals are sensitive operations and often have time limits or require specific conditions to be met.

*   **Register URL (for C2B):**
    *   *What it is:* This API is specifically for configuring the **callback URLs** for C2B transactions. It tells Mpesa where to send validation and confirmation messages for payments made to your Paybill/Till number.
    *   *How it works:* Your application sends a request specifying your **Validation URL** (where Mpesa sends a request *before* completing a C2B transaction, allowing your system to accept or reject it) and your **Confirmation URL** (where Mpesa sends a notification *after* a C2B transaction is successfully completed).
    *   *Importance of Secure Callbacks:* These URLs must be publicly accessible and secured with **HTTPS** (Hypertext Transfer Protocol Secure). They are critical for your application to receive real-time updates on incoming payments.

> 💡 **What is happening here:** You choose which Mpesa services your application needs, like accepting payments or sending money. Each service has specific requirements, and selecting only what's necessary improves security by limiting what your application can do.

**Why Select Specific APIs?**
*   **Security:** Limiting API access reduces the **attack surface**. If an application's credentials are compromised, an attacker can only access the functionalities that have been explicitly enabled.
*   **Clarity:** Selecting specific APIs makes it clear exactly what the application is designed to do.
*   **Performance (Indirect):** While not directly impacting API call performance, a leaner application with fewer enabled features might be simpler to manage and secure, which indirectly contributes to overall system stability.

*UI Walkthrough:* The API selection section typically presents a list of API names, each with a checkbox next to it. You simply click the checkbox for every API your application will use. For a basic e-commerce setup, you would likely select Mpesa Express, C2B, B2C, Transaction Status, and potentially Reversal.

**4.4. Generating Sandbox Credentials**

After you have named your application and selected the APIs it will use, the Daraja portal will either generate or prompt you to generate the necessary credentials. These credentials are unique to your sandbox application and are completely separate from any production credentials.

*   **Consumer Key:**
    *   *What it is:* This is a unique identifier for your application. It is publicly visible in the sense that it's part of every API request, but its purpose is to identify *your specific application* to the Daraja platform.
    *   *Purpose:* It is used together with the Consumer Secret to obtain an **OAuth 2.0 Access Token**. It tells the Daraja authentication server which client (your application) is requesting a token.
    *   *Format:* Typically a long alphanumeric string.

*   **Consumer Secret:**
    *   *What it is:* This is a confidential string that acts like a password for your application. It must be kept absolutely secret and should never be exposed in client-side code, public code repositories, or insecure communication channels.
    *   *Purpose:* It is used with the Consumer Key to authenticate your application and obtain an **OAuth 2.0 Access Token**. The Daraja server verifies that the provided Consumer Secret matches the one associated with the Consumer Key.
    *   *Format:* Typically a long alphanumeric string.

*   **Passkey (for STK Push - Mpesa Express):**
    *   *What it is:* This is a unique key specifically used in conjunction with the Mpesa Express (STK Push) API. It serves as a security measure to ensure that only authorized applications can initiate STK Push requests.
    *   *Purpose:* The Passkey is *not* sent directly in the API request. Instead, it is combined with the business shortcode and a timestamp, then encoded using **Base64** to form the `Password` parameter in the STK Push request. This dynamic password generation adds an extra layer of security, making it harder for unauthorized parties to forge STK Push requests.
    *   *Format:* Typically a long alphanumeric string.

*   **Shortcode (Paybill/Till Number):**
    *   *What it is:* In the sandbox environment, Safaricom provides specific test shortcodes (Paybill or Till Numbers) that you can use for simulating transactions. These are not real-world shortcodes.
    *   *Purpose:* To identify the business account involved in a transaction. For C2B, it's the number customers pay to. For STK Push, B2C, B2B, Account Balance, Transaction Status, and Reversal, it identifies the business initiating or receiving funds.
    *   *Sandbox Example:* Common sandbox shortcodes include `600999` (for Paybill) or `174379` (for STK Push, which is also a Paybill number). The portal will typically display the sandbox shortcode(s) associated with your application.

*   **Initiator Username and Security Credential (for B2C/B2B/Reversal/Account Balance/Transaction Status):**
    *   *What they are:* These are required for APIs that involve the business initiating a transaction that moves funds *out* of its account (B2C, B2B, Reversal) or querying sensitive account information (Account Balance, Transaction Status).
        *   **Initiator Username:** A username linked to the business's Mpesa account that is authorized to perform these specific operations.
        *   **Security Credential:** An encrypted string that represents the password for the Initiator Username. This password is encrypted using a **public key** provided by Safaricom, ensuring it is transmitted securely.
    *   *Purpose:* To provide an additional layer of authentication and authorization for sensitive outbound transactions. It ensures that only authorized personnel or systems within the business can initiate these types of operations.
    *   *How to Generate the Encrypted Security Credential:* This is a multi-step process:
        1.  **Obtain Safaricom's Public Certificate:** Safaricom provides a specific public key certificate (e.g., a `.cer` file) that is used for encrypting the Initiator password. This certificate is specific to the environment (sandbox vs. production).
        2.  **Encrypt the Initiator Password:** Using a cryptographic library (e.g., OpenSSL, Java Cryptography Architecture, Python's `cryptography` library), the Initiator password is encrypted using Safaricom's public key. The encryption algorithm is typically **RSA** with **OAEP padding**.
        3.  **Base64 Encode:** The resulting encrypted binary data is then encoded using **Base64** to produce a string that can be safely transmitted in JSON or XML requests.
    *   *Sandbox Specifics:* For the sandbox, you will typically use a test Initiator Username (e.g., `testapi`) and a simple password (e.g., `Safaricom999!`). You will need to download the sandbox public certificate from the Daraja portal or documentation to perform the encryption.

> 💡 **What is happening here:** The portal generates unique keys and identifiers for your application. These include a Consumer Key and Secret for general access, a Passkey for STK Push, and an Initiator Username/Security Credential for sensitive transactions like sending money. These are all crucial for your application to securely communicate with Mpesa.

**Relationship between Credentials and OAuth 2.0:**
The **Consumer Key** and **Consumer Secret** are the primary credentials used to obtain an **Access Token** through the **OAuth 2.0 Client Credentials Grant flow**. This Access Token is a **bearer token**, meaning anyone who possesses it can use it, and it grants temporary access to the Mpesa APIs. All subsequent API calls (e.g., STK Push, C2B, B2C) will include this Access Token in the `Authorization` header (e.g., `Authorization: Bearer <access_token>`). The other credentials (Passkey, Initiator Username, Security Credential) are then used *within* the data payload of specific API requests for their respective functionalities, providing an additional layer of transaction-specific security.

*UI Walkthrough:* After selecting APIs and clicking "Create App" (or a similar button), the portal will display a summary page for your new application. This page will prominently feature the generated Consumer Key and Consumer Secret. It will also list the sandbox shortcodes and provide instructions or links to download the sandbox public certificate for encrypting the Initiator password. *It is crucial to copy and securely store the Consumer Secret immediately, as it is often shown only once and cannot be retrieved later.* If lost, it must be regenerated.

**4.5. Viewing and Managing App Details**

Once the sandbox application is created, you will be redirected to its detail page or back to the "My Apps" list.

*   **Dashboard View of the Newly Created App:**
    *   Clicking on the app name from the "My Apps" list will take you to its dedicated dashboard.
    *   This page typically displays:
        *   The App Name and Description.
        *   The Consumer Key (often partially hidden for security).
        *   An option to reveal or copy the Consumer Secret (if it's still available, or to regenerate it).
        *   A list of the APIs you enabled for this application.
        *   The Sandbox Shortcodes.
        *   Links to download necessary certificates.
        *   Usage statistics (primarily for production applications).
        *   Options to edit the app's details or delete the app.

*   **How to Retrieve Credentials Later:**
    *   The Consumer Key is usually always visible on the app's detail page.
    *   The Consumer Secret is often only shown once immediately after creation. If you lose it, you will need to regenerate it. Regenerating a secret invalidates the old one, meaning any applications using the old secret will stop working until they are updated with the new one.
    *   Passkeys and Initiator details are typically displayed on the app's detail page.

*   **Options for Regenerating Keys:**
    *   The Daraja portal provides buttons or links such as "Regenerate Consumer Secret" or "Regenerate Passkey."
    *   *Why regenerate?*
        *   **Security Compromise:** If you suspect your secret key has been exposed or compromised.
        *   **Security Policy:** Many organizations have policies that require periodic key rotation.
        *   **Loss:** If you failed to save the secret when it was first displayed.
    *   *Impact of Regeneration:* Regenerating a key immediately invalidates the previous key. Any running application using the old key will fail to authenticate until it is updated with the new key. This requires careful coordination, especially in production environments. In a sandbox, the impact is minimal, but it's good practice to understand the implications.

> 💡 **What is happening here:** After creating your app, you can view all its details and credentials on its dedicated dashboard. It's crucial to securely save your Consumer Secret immediately, as it's often shown only once. You can also regenerate keys if needed, but this will invalidate old keys.

### 5. Deep-Dive Analysis Blocks

To provide a comprehensive understanding, let's explore some critical aspects in more detail.

**5.1. Case Study: A Typical E-commerce Sandbox Setup**

Consider an e-commerce platform named "ShopSmart" that needs to integrate Mpesa payments for its online store. ShopSmart wants to allow customers to pay using **STK Push** (for a smooth checkout experience) and also via **C2B** (for customers who prefer to initiate payments manually). Additionally, ShopSmart needs to process refunds to customers and pay its suppliers.

**Scenario Requirements:**
1.  Accept payments from customers using STK Push.
2.  Accept payments from customers via C2B (Paybill).
3.  Process refunds to customers.
4.  Pay suppliers (other businesses).
5.  Check the status of any transaction.
6.  Monitor its Mpesa account balance.

**Walkthrough of API Selections and Why:**

1.  **Mpesa Express (STK Push):** *Selected.* This is essential for initiating payment requests directly to customers' phones for online checkout.
2.  **C2B (Customer to Business):** *Selected.* This is needed to receive payments from customers who manually pay to ShopSmart's Paybill number.
3.  **B2C (Business to Customer):** *Selected.* This is required for processing refunds to individual customers.
4.  **B2B (Business to Business):** *Selected.* This is necessary for ShopSmart to pay its suppliers.
5.  **Transaction Status:** *Selected.* This is crucial for verifying payment success, handling delayed confirmations, and providing customer support.
6.  **Account Balance:** *Selected.* This is important for monitoring the business's Mpesa liquidity and for reconciliation purposes.
7.  **Reversal:** *Selected.* While B2C can handle refunds, Reversal is specifically for undoing a *previous* transaction, which might be needed if a customer overpays or an order is canceled immediately after payment.
8.  **Register URL:** *Selected.* This is vital for C2B payments. ShopSmart needs to register a **Confirmation URL** to receive real-time notifications when a customer pays its Paybill number. A **Validation URL** might also be registered if ShopSmart wants to validate incoming payments before they are completed (e.g., checking if an account number is valid).

> 💡 **What is happening here:** For an e-commerce business like ShopSmart, a wide range of Mpesa APIs are needed to handle various payment scenarios, from customer payments to refunds and supplier payouts. Each API serves a specific function to meet the business's operational needs.

**Credentials Needed for Each Operation:**

*   **Global Authentication (OAuth 2.0):**
    *   **Consumer Key:** Identifies ShopSmart's application.
    *   **Consumer Secret:** Authenticates ShopSmart's application to obtain an **Access Token**.
    *   **Access Token:** Obtained using the Consumer Key and Secret, included in the `Authorization` header for all API calls.

*   **Mpesa Express (STK Push):**
    *   **Passkey:** Used to generate the `Password` parameter in the STK Push request payload.
    *   **Sandbox Shortcode:** The Paybill number (e.g., `174379`) to which payments are directed.

*   **C2B (Customer to Business):**
    *   **Sandbox Shortcode:** The Paybill number (e.g., `600999`) customers will pay to.
    *   **Confirmation URL:** The endpoint on ShopSmart's server where Mpesa will send payment confirmations.
    *   **Validation URL (Optional):** The endpoint on ShopSmart's server where Mpesa will send validation requests before completing a C2B transaction.

*   **B2C (Business to Customer), B2B (Business to Business), Account Balance, Transaction Status, Reversal:**
    *   **Initiator Username:** The authorized username (e.g., `testapi`).
    *   **Security Credential:** The encrypted password for the Initiator Username, generated using Safaricom's public sandbox certificate.
    *   **Sandbox Shortcode:** The business's own shortcode from which funds are disbursed or whose balance is queried.

> 💡 **What is happening here:** Different Mpesa operations require specific credentials. A Consumer Key and Secret are used for general access, while Passkeys, Shortcodes, Initiator Usernames, and Security Credentials are needed for particular transaction types like STK Push or B2C payments.

**How These Credentials Would Be Used in a Hypothetical Application:**

ShopSmart's backend application (e.g., a Python Flask or Node.js Express server) would:

1.  **Store Credentials Securely:** The Consumer Key, Consumer Secret, Passkey, Initiator Username, and the encrypted Security Credential would be stored as **environment variables** or in a secure **secret management system** (e.g., AWS Secrets Manager, HashiCorp Vault). The sandbox public certificate would also be stored securely for encryption purposes.
2.  **Obtain Access Token:** Before making any Mpesa API call, the application would first send a **POST request** to the Daraja OAuth endpoint (`https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials`). This request would use the Consumer Key and Consumer Secret (Base64 encoded as `ConsumerKey:ConsumerSecret` in the `Authorization: Basic` header). The response from this request would contain the `access_token`.
3.  **Make API Calls:**
    *   **STK Push:** When a customer checks out, the application constructs an STK Push request payload. This payload includes the customer's phone number, the amount, the business shortcode, and a dynamically generated `Password` (created from the Passkey, shortcode, and a timestamp). It then sends this to the STK Push endpoint with the Access Token in the `Authorization: Bearer` header.
    *   **C2B Confirmation:** When a customer pays via C2B, Mpesa sends a POST request to ShopSmart's configured Confirmation URL. The application then processes this callback to update the order status.
    *   **B2C Refund:** To issue a refund, the application constructs a B2C request payload. This includes the customer's phone number, the amount, the business shortcode, the Initiator Username, and the encrypted Security Credential. It sends this to the B2C endpoint with the Access Token.
    *   **Transaction Status Check:** To check a transaction, the application constructs a request with the transaction ID, business shortcode, Initiator Username, and Security Credential. It then sends this to the Transaction Status endpoint with the Access Token.

This case study illustrates how the selection of APIs directly translates into the specific credentials required and the operational flow within a real-world application.

> 💡 **What is happening here:** A real application uses its securely stored credentials to first get an Access Token, which acts like a temporary pass. Then, it uses this token along with other specific credentials to make various Mpesa API calls, such as initiating payments or processing refunds.

**5.2. Under the Hood: OAuth 2.0 and Daraja Authentication**

The Mpesa Daraja API uses **OAuth 2.0** for authentication and authorization. Specifically, it employs the **Client Credentials Grant** flow. This flow is ideal for server-to-server communication where an application needs to access its own resources, or resources it has been authorized to access, without direct involvement from an end-user.

**What is OAuth 2.0?**
**OAuth 2.0** is an authorization framework that allows an application to gain limited access to a user's (or, in this case, a business's) resources on an HTTP service. It does this without requiring the application to know or store the user's actual credentials. This is achieved through the issuance of **Access Tokens**.

> 💡 **What is happening here:** OAuth 2.0 is a standard way for applications to get permission to access resources without needing the user's password. It works by giving out temporary "Access Tokens."

**The Client Credentials Grant Flow (Daraja Implementation):**

1.  **Application Registration:** As we've seen, the developer registers an application with the Daraja portal. During this process, the **Daraja Authorization Server** (Safaricom's authentication system) issues a unique **Client ID** (which is your **Consumer Key**) and a **Client Secret** (which is your **Consumer Secret**) to the application.
2.  **Request for Access Token:** When your application needs to make an API call, it first sends a request to the Daraja Authorization Server's token endpoint. This request includes:
    *   `grant_type=client_credentials`: This parameter explicitly states that the application is using the Client Credentials Grant flow.
    *   `Authorization` header: This header contains the `Client ID` and `Client Secret`, which are encoded using **Base64**. The format is `Basic <base64_encoded(ConsumerKey:ConsumerSecret)>`.

    *Example HTTP Request to obtain token:*
    ```http
    POST /oauth/v1/generate?grant_type=client_credentials HTTP/1.1
    Host: sandbox.safaricom.co.ke
    Authorization: Basic Y29uc3VtZXJrZXk6Y29uc3VtZXJzZWNyZXQ=
    Content-Type: application/json
    ```
    (Where `Y29uc3VtZXJrZXk6Y25zdW1lcnNlY3JldA==` is the Base64 encoding of `consumerkey:consumersecret`)

3.  **Authorization Server Validation:** The Daraja Authorization Server receives this request. It then validates the provided `Client ID` and `Client Secret`. If they are valid and match a registered application, the server proceeds to issue an Access Token.
4.  **Issuance of Access Token:** The Authorization Server responds with a **JSON** (JavaScript Object Notation) object. This object contains the `access_token` and its `expires_in` value, which indicates its lifetime in seconds.

    *Example HTTP Response (Token):*
    ```json
    {
        "access_token": "YOUR_GENERATED_ACCESS_TOKEN_STRING",
        "expires_in": "3599"
    }
    ```
    The `access_token` is typically a long, opaque string (often a **JWT** - JSON Web Token, though its internal structure is not usually relevant to the client).

5.  **Using the Access Token for API Calls:** Your application then includes this `access_token` in the `Authorization` header of all subsequent requests to the Mpesa API endpoints. The format is `Authorization: Bearer <access_token>`.

    *Example HTTP Request to an Mpesa API endpoint:*
    ```http
    POST /mpesa/stkpush/v1/processrequest HTTP/1.1
    Host: sandbox.safaricom.co.ke
    Authorization: Bearer YOUR_GENERATED_ACCESS_TOKEN_STRING
    Content-Type: application/json

    {
        "BusinessShortCode": "174379",
        "Password": "...",
        "Timestamp": "...",
        "TransactionType": "CustomerPayBillOnline",
        "Amount": "1",
        "PartyA": "254708374149",
        "PartyB": "174379",
        "PhoneNumber": "254708374149",
        "CallBackURL": "https://mydomain.com/path",
        "AccountReference": "CompanyXLTD",
        "TransactionDesc": "Payment of X"
    }
    ```

> 💡 **What is happening here:** Your application first uses its Consumer Key and Secret to ask the Daraja Authorization Server for a temporary Access Token. Once it receives this token, it includes it in all future requests to Mpesa APIs to prove it's authorized.

**Token Expiry and Refresh:**
Daraja Access Tokens are typically short-lived, often lasting for about 1 hour (or 3600 seconds). This is a security best practice: if a token is compromised, its usefulness is limited by its short lifespan. Daraja does not typically implement a "refresh token" mechanism for the Client Credentials Grant. Instead, when an Access Token expires, the application simply requests a new one using its `Consumer Key` and `Consumer Secret`. Applications should implement logic to check token expiry and automatically request a new token when needed or upon receiving an "unauthorized" error (e.g., HTTP 401) due to an expired token.

**Sequence diagram: getting a token, then calling the API**

![OAuth sequence: your server gets an access token from Daraja OAuth using Basic auth, caches it, then calls the Daraja API with the token as a Bearer header.](diagrams/oauth-sequence.svg)

This sequence diagram visually represents the flow: your application first authenticates with the Daraja Authorization Server to get a token, and then uses that token to authorize requests to the actual Mpesa API endpoints.

**5.3. Failure Modes, Pitfalls & Misconceptions**

Understanding common pitfalls is as important as understanding the correct procedure. These are frequent issues developers encounter:

*   **Incorrect API Selection:**
    *   *What happens:* If you don't select an API (e.g., Mpesa Express) during app creation, your application will receive an authorization error (e.g., HTTP 403 Forbidden) when it tries to call that specific API. This happens even if you have a valid Access Token. The Access Token only grants access to the *application*, but the application itself must have permissions for the *specific API*.
    *   *Remedy:* Go back to the Daraja portal, edit your application, and enable the required API.

*   **Mismanaging Consumer Secret:**
    *   *What happens:* Hardcoding the Consumer Secret directly into your source code, committing it to a public version control repository (like GitHub), or exposing it in client-side JavaScript. This makes your application vulnerable. An attacker could use your Consumer Key and Secret to generate Access Tokens and potentially perform unauthorized transactions.
    *   *Remedy:* Always store secrets in **environment variables**, dedicated **secret management services** (e.g., AWS Secrets Manager, Azure Key Vault, HashiCorp Vault), or secure configuration files that are not committed to version control. Never expose them on the client-side.

*   **Incorrect Passkey Usage (for STK Push):**
    *   *What happens:* The Passkey itself is *not* sent in the STK Push request. A common error is sending the raw Passkey or incorrectly generating the `Password` parameter. The `Password` parameter is a Base64 encoded string of `BusinessShortCode + Passkey + Timestamp`. If this is incorrect, the STK Push request will fail with an authentication error.
    *   *Remedy:* Double-check the exact concatenation and Base64 encoding logic. Ensure the `Timestamp` format is `YYYYMMDDHHmmss` (e.g., `20261019153000`) and matches the timestamp used in the request.

*   **Sandbox vs. Production Credential Confusion:**
    *   *What happens:* Using sandbox Consumer Key/Secret with production API endpoints, or vice-versa. This will always result in authentication failures. Sandbox credentials only work with sandbox endpoints (`sandbox.safaricom.co.ke`), and production credentials only work with production endpoints (`api.safaricom.co.ke`).
    *   *Remedy:* Maintain strict separation between sandbox and production configurations. Use environment variables to switch between endpoint URLs and credentials based on the deployment environment.

*   **Callback URL Misconfiguration:**
    *   *What happens:* For C2B confirmations or STK Push callbacks, if the `CallBackURL` is incorrect, inaccessible, not HTTPS, or not publicly resolvable, your application will not receive transaction notifications. This leads to a disconnect between Mpesa's transaction status and your application's state.
    *   *Remedy:* Ensure callback URLs are publicly accessible, use HTTPS, are correctly spelled, and your server is configured to receive POST requests at that endpoint. During development, tools like `ngrok` can expose local development servers to the internet for testing callbacks.

*   **Security Credential Generation Errors (for B2C/B2B/Reversal):**
    *   *What happens:* Errors in encrypting the Initiator password, such as using the wrong public certificate (e.g., production certificate for sandbox), incorrect encryption algorithm (e.g., RSA/ECB/PKCS1Padding instead of RSA/ECB/OAEPWithSHA-256AndMGF1Padding or similar), or incorrect Base64 encoding. This will lead to authentication failures for these sensitive APIs.
    *   *Remedy:* Always use the *correct environment's public certificate* (sandbox certificate for sandbox, production for production). Verify the encryption algorithm and padding scheme specified in Daraja documentation. Use reliable cryptographic libraries.

*   **Expired Access Tokens:**
    *   *What happens:* If an API call is made with an expired Access Token, the Daraja API will return an HTTP 401 Unauthorized error.
    *   *Remedy:* Implement token caching and refresh logic. Store the Access Token and its expiry time. Before making an API call, check if the token is expired or about to expire. If so, request a new token.

> 💡 **What is happening here:** Common mistakes include not enabling the right APIs, exposing secret keys, incorrectly generating passwords for STK Push, mixing up sandbox and production credentials, and misconfiguring callback URLs or security credentials. These errors lead to authentication failures and prevent your application from working correctly.

**5.4. Security Implications of Sandbox App Creation**

Even though the sandbox environment does not involve real money, the credentials generated for it still hold significant value and must be protected.

*   **Why even sandbox credentials need to be protected:**
    *   **Intellectual Property:** Your sandbox application configuration, API selections, and even the mere existence of your integration plans can be sensitive information.
    *   **Abuse Potential:** While not directly financial, compromised sandbox credentials could be used to flood the sandbox environment with requests. This could potentially impact other developers' testing or even lead to rate limiting for your account.
    *   **Precursor to Production:** Poor security practices in the sandbox often translate to poor security practices in production. Establishing good habits early is crucial. If developers get used to hardcoding sandbox secrets, they might inadvertently do the same for production secrets.
    *   **Phishing/Social Engineering:** Compromised sandbox credentials could be used as part of a larger **social engineering** attack to gain access to more sensitive systems or information.

> 💡 **What is happening here:** Even though sandbox credentials don't involve real money, they still need strong protection. This is because they can reveal sensitive information, be abused to disrupt testing, lead to bad security habits for production, or be used in larger cyberattacks.

*   **Best practices for storing API keys:**
    *   **Environment Variables:** This is the most common and recommended method for development and deployment. Secrets are loaded from the environment at runtime and are not part of the codebase itself.
    *   **Secret Management Services:** For production environments and larger teams, services like AWS Secrets Manager, Azure Key Vault, Google Secret Manager, or HashiCorp Vault provide centralized, secure storage, access control, and rotation capabilities for secrets.
    *   **Configuration Files (Securely Managed):** If using configuration files, ensure they are located outside the web root, have restricted file permissions, and are explicitly excluded from version control (e.g., via a `.gitignore` file).
    *   **Never Hardcode:** Avoid embedding API keys directly into your source code.
    *   **Never Commit to Version Control:** Ensure `.gitignore` rules prevent secret files or environment variable files from being committed to Git or other **VCS** (Version Control Systems).

*   **The role of IP whitelisting:**
    *   **What it is:** **IP whitelisting** is a security measure where the API provider (Safaricom) is configured to only accept API requests originating from a predefined list of approved IP addresses.
    *   **In Daraja:** While less common for sandbox environments, IP whitelisting is a critical security feature for production Daraja applications, especially for sensitive APIs like B2C, B2B, and Reversal. It adds an extra layer of defense: even if your credentials are stolen, an attacker cannot use them unless they originate from a whitelisted IP address.
    *   **Sandbox Context:** For the sandbox, IP whitelisting is usually not enforced, allowing developers to test from various development environments. However, it's important to be aware of its existence and plan for its implementation in production.

> 💡 **What is happening here:** To keep API keys safe, they should never be hardcoded or committed to public repositories. Instead, use environment variables or dedicated secret management services. Additionally, IP whitelisting is a powerful security feature in production that restricts API access to only approved network locations.

### 6. Code/Implementation Examples

Let's walk through a Python example demonstrating how to set up environment variables, obtain an OAuth token, and make a simple API call in the sandbox.

**Prerequisites:**
*   Python 3.x installed.
*   `requests` library: `pip install requests`
*   `cryptography` library: `pip install cryptography` (for encrypting Initiator password)

**6.1. Setting up Environment Variables**

Create a file named `.env` in your project root (and add `.env` to your `.gitignore`):

```
# .env file
# --- Sandbox Credentials ---
DARJA_SANDBOX_CONSUMER_KEY="your_sandbox_consumer_key"
DARJA_SANDBOX_CONSUMER_SECRET="your_sandbox_consumer_secret"
DARJA_SANDBOX_PASSKEY="your_sandbox_passkey"
DARJA_SANDBOX_SHORTCODE_STK="174379" # Example STK Push shortcode
DARJA_SANDBOX_SHORTCODE_C2B="600999" # Example C2B shortcode
DARJA_SANDBOX_INITIATOR_USERNAME="testapi"
DARJA_SANDBOX_INITIATOR_PASSWORD="Safaricom999!" # This will be encrypted
DARJA_SANDBOX_PUBLIC_CERT_PATH="./sandbox_cert.cer" # Path to your downloaded sandbox certificate
DARJA_SANDBOX_CALLBACK_URL="https://your-ngrok-url.ngrok.io/mpesa-callback" # Replace with your actual callback URL
```
**Note:** Replace placeholder values with your actual sandbox credentials obtained from the Daraja portal. Download the `sandbox_cert.cer` file from the Daraja portal and place it in your project directory.

**6.2. Python Code for Token Generation and API Call**

Create a Python file, e.g., `mpesa_sandbox_client.py`:

```python
import os
import base64
import requests
import datetime
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

# Load environment variables from .env file
load_dotenv()

# --- Configuration from Environment Variables ---
SANDBOX_CONSUMER_KEY = os.getenv("DARJA_SANDBOX_CONSUMER_KEY")
SANDBOX_CONSUMER_SECRET = os.getenv("DARJA_SANDBOX_CONSUMER_SECRET")
SANDBOX_PASSKEY = os.getenv("DARJA_SANDBOX_PASSKEY")
SANDBOX_SHORTCODE_STK = os.getenv("DARJA_SANDBOX_SHORTCODE_STK")
SANDBOX_INITIATOR_USERNAME = os.getenv("DARJA_SANDBOX_INITIATOR_USERNAME")
SANDBOX_INITIATOR_PASSWORD = os.getenv("DARJA_SANDBOX_INITIATOR_PASSWORD")
SANDBOX_PUBLIC_CERT_PATH = os.getenv("DARJA_SANDBOX_PUBLIC_CERT_PATH")
SANDBOX_CALLBACK_URL = os.getenv("DARJA_SANDBOX_CALLBACK_URL")

# --- Daraja Sandbox Endpoints ---
SANDBOX_BASE_URL = "https://sandbox.safaricom.co.ke"
AUTH_URL = f"{SANDBOX_BASE_URL}/oauth/v1/generate"
STK_PUSH_URL = f"{SANDBOX_BASE_URL}/mpesa/stkpush/v1/processrequest"
ACCOUNT_BALANCE_URL = f"{SANDBOX_BASE_URL}/mpesa/accountbalance/v1/query"

# --- Helper Functions ---

def get_access_token():
    """
    Obtains an OAuth 2.0 Access Token from Daraja.
    """
    try:
        # Concatenate Consumer Key and Secret, then Base64 encode
        credentials = f"{SANDBOX_CONSUMER_KEY}:{SANDBOX_CONSUMER_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode('utf-8')

        headers = {
            "Authorization": f"Basic {encoded_credentials}"
        }
        params = {
            "grant_type": "client_credentials"
        }

        print("Requesting Access Token...")
        response = requests.get(AUTH_URL, headers=headers, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in")

        if access_token:
            print(f"Access Token obtained. Expires in {expires_in} seconds.")
            return access_token
        else:
            print("Failed to get access token:", token_data)
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting access token: {e}")
        return None

def generate_stk_password(timestamp):
    """
    Generates the Mpesa Express (STK Push) password.
    Password = Base64Encode(BusinessShortCode + Passkey + Timestamp)
    """
    data_to_encode = f"{SANDBOX_SHORTCODE_STK}{SANDBOX_PASSKEY}{timestamp}"
    encoded_password = base64.b64encode(data_to_encode.encode()).decode('utf-8')
    return encoded_password

def encrypt_initiator_password(password):
    """
    Encrypts the Initiator password using Safaricom's public certificate.
    """
    try:
        with open(SANDBOX_PUBLIC_CERT_PATH, "rb") as cert_file:
            public_key = serialization.load_pem_public_key(cert_file.read())

        encrypted_password = public_key.encrypt(
            password.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(encrypted_password).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: Public certificate file not found at {SANDBOX_PUBLIC_CERT_PATH}")
        return None
    except Exception as e:
        print(f"Error encrypting initiator password: {e}")
        return None

# --- Main API Call Functions ---

def simulate_stk_push(access_token, phone_number, amount, account_reference, transaction_desc):
    """
    Simulates an Mpesa Express (STK Push) transaction.
    """
    if not access_token:
        print("No access token available for STK Push.")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    stk_password = generate_stk_password(timestamp)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "BusinessShortCode": SANDBOX_SHORTCODE_STK,
        "Password": stk_password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline", # Or CustomerBuyGoodsOnline
        "Amount": amount,
        "PartyA": phone_number, # Customer's phone number
        "PartyB": SANDBOX_SHORTCODE_STK, # Business Short Code
        "PhoneNumber": phone_number, # Customer's phone number
        "CallBackURL": SANDBOX_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_desc
    }

    print(f"\nInitiating STK Push for {phone_number} with amount {amount}...")
    try:
        response = requests.post(STK_PUSH_URL, json=payload, headers=headers)
        response.raise_for_status()
        print("STK Push Response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error during STK Push: {e}")
        if e.response is not None:
            print("Error Response Body:", e.response.json())

def query_account_balance(access_token):
    """
    Queries the Mpesa account balance for the business shortcode.
    """
    if not access_token:
        print("No access token available for Account Balance query.")
        return

    encrypted_initiator_cred = encrypt_initiator_password(SANDBOX_INITIATOR_PASSWORD)
    if not encrypted_initiator_cred:
        print("Failed to encrypt initiator password. Cannot query account balance.")
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "Initiator": SANDBOX_INITIATOR_USERNAME,
        "SecurityCredential": encrypted_initiator_cred,
        "CommandID": "AccountBalance",
        "PartyA": SANDBOX_SHORTCODE_STK, # The shortcode whose balance is being queried
        "IdentifierType": "4", # 4 for shortcode, 2 for till number
        "Remarks": "Check balance",
        "QueueTimeOutURL": SANDBOX_CALLBACK_URL, # URL for timeout notifications
        "ResultURL": SANDBOX_CALLBACK_URL # URL for result notifications
    }

    print(f"\nQuerying Account Balance for {SANDBOX_SHORTCODE_STK}...")
    try:
        response = requests.post(ACCOUNT_BALANCE_URL, json=payload, headers=headers)
        response.raise_for_status()
        print("Account Balance Response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error querying Account Balance: {e}")
        if e.response is not None:
            print("Error Response Body:", e.response.json())

# --- Main Execution ---
if __name__ == "__main__":
    # 1. Get Access Token
    token = get_access_token()

    if token:
        # 2. Simulate an STK Push
        # Use a valid Safaricom number for testing. In sandbox, any 2547... number works.
        test_phone = "254708374149" # Replace with a test Safaricom number
        test_amount = "1" # Minimum amount for STK Push is usually 1 KES
        test_account_ref = "ORDER12345"
        test_transaction_desc = "Test Payment for Order"
        simulate_stk_push(token, test_phone, test_amount, test_account_ref, test_transaction_desc)

        # 3. Query Account Balance
        query_account_balance(token)
    else:
        print("Could not proceed without an Access Token.")

```

**Line-by-Line Operational Explanation:**

1.  **`import os, base64, requests, datetime`**: These lines import standard Python libraries. `os` helps interact with the operating system (like getting environment variables), `base64` handles Base64 encoding, `requests` is used for making HTTP requests, and `datetime` helps with date and time operations.
2.  **`from dotenv import load_dotenv`**: This imports the `load_dotenv` function from the `python-dotenv` library. This function is used to load variables from a `.env` file into the program's environment.
3.  **`from cryptography.hazmat.primitives import serialization, hashes`**: These lines import cryptographic primitives from the `cryptography` library. `serialization` is for loading public keys, and `hashes` is for cryptographic hashing algorithms.
4.  **`from cryptography.hazmat.primitives.asymmetric import padding`**: This imports padding schemes, specifically for **RSA encryption**.
5.  **`load_dotenv()`**: This function call reads the `.env` file in your project directory and populates `os.environ` with the key-value pairs defined in that file. This makes your credentials accessible as environment variables.
6.  **`SANDBOX_CONSUMER_KEY = os.getenv("DARJA_SANDBOX_CONSUMER_KEY")`**: This line retrieves the value of the `DARJA_SANDBOX_CONSUMER_KEY` environment variable. This pattern is repeated for all credentials, ensuring they are loaded from a secure external source rather than being hardcoded directly in the script.
7.  **`SANDBOX_BASE_URL = "https://sandbox.safaricom.co.ke"`**: This defines the base URL for all API calls made to the Daraja sandbox environment.
8.  **`AUTH_URL = f"{SANDBOX_BASE_URL}/oauth/v1/generate"`**: This constructs the complete URL for the OAuth token endpoint, which is where your application requests an Access Token.
9.  **`get_access_token()` function:**
    *   `credentials = f"{SANDBOX_CONSUMER_KEY}:{SANDBOX_CONSUMER_SECRET}"`: This combines your Consumer Key and Secret with a colon in between.
    *   `encoded_credentials = base64.b64encode(credentials.encode()).decode('utf-8')`: This line encodes the combined string into **Base64**. This Base64-encoded string is required for the `Basic` authentication header when requesting an Access Token.
    *   `headers = {"Authorization": f"Basic {encoded_credentials}"}`:

---

[← Secure credential storage](06-secure-credential-storage.md) · [Index](README.md)
