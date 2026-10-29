# google-ads

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## data-manager-api-audience-ingestion
Guides developers through managing (adding, removing, and clearing) audience members for Google products using the Data Manager API and its associated client libraries. Use this skill when the user wants to upload audience members, remove specific users, or clear/replace an entire audience for Customer Match, mobile device ID audiences, or any other audience use case supported by the Data Manager API. Don't use for uploading events or conversions (use the data-manager-api-event-ingestion skill).

Read: `library/ads/data-manager-api-audience-ingestion/INSTRUCTIONS.md`

## data-manager-api-event-ingestion
Guides developers through implementing event and conversion ingestion to Google products using the Data Manager API /v1/events/ingest endpoint and its associated client libraries. Use this skill when the user wants to upload offline conversions, enhanced conversions for leads, click conversions, Google Analytics web or app events, or any other event ingestion use case supported by the Data Manager API. Don't use for uploading audience members (use the data-manager-api-audience-ingestion skill).

Read: `library/ads/data-manager-api-event-ingestion/INSTRUCTIONS.md`

## data-manager-api-setup
Guides developers through client library installation and authentication setup steps for the Data Manager API. Use this skill when a user is getting started with the Data Manager API and needs to setup their local environment, install the client library, or setup access to the API. Don't use for implementing audience or event ingestion logic (use the data-manager-api-audience-ingestion or data-manager-api-event-ingestion skills instead).

Read: `library/ads/data-manager-api-setup/INSTRUCTIONS.md`

## google-ads-api-account-diagnostics
Diagnoses Google Ads account performance issues such as conversion loss (value or volume), low lead flow/volume, and lost impression share (opportunities) due to ad rank, bids, or budgets. Use when troubleshooting sudden performance drops, analyzing campaign impression share metrics, investigating low lead flow, or searching for bidding and budget constraints. Don't use for setting up new campaigns, uploading conversion events directly, or general Google Mobile Ads SDK integration issues (use gma-android-integrate instead).

Read: `library/ads/google-ads-api-account-diagnostics/INSTRUCTIONS.md`

## google-ads-api-mcp-setup
Guides developers through downloading, configuring, and installing the official open-source Google Ads MCP Server. Use this skill when a user wants to connect their AI assistant (such as Gemini, Claude Code, or Cursor) to their Google Ads account to query campaigns or retrieve reporting metrics using natural language.

Read: `library/ads/google-ads-api-mcp-setup/INSTRUCTIONS.md`

## google-ads-api-quickstart
Guides developers through Google Ads API quickstart: credential setup, choosing from 6 client libraries/REST, configuring environments, and running a "retrieve campaigns" script. Troubleshoots common setup errors: USER_PERMISSION_DENIED, login_customer_id issues, and DEVELOPER_TOKEN_NOT_APPROVED. Use this skill when: - The user asks how to get started with the Google Ads API. - The user needs to set up Google Ads credentials or developer tokens. - The user wants to write a quickstart/example script for Google Ads. - The user encounters errors like USER_PERMISSION_DENIED or DEVELOPER_TOKEN_NOT_APPROVED.

Read: `library/ads/google-ads-api-quickstart/INSTRUCTIONS.md`

## google-mobile-ads-android-migrate-to-next-gen
Migrates Android applications from the old, legacy Google Mobile Ads (GMA) SDK (com.google.android.gms:play-services-ads) to the new GMA Next-Gen SDK (com.google.android.libraries.ads.mobile.sdk:ads-mobile-sdk). Provides comprehensive mapping tables for imports, classes, and method signatures to help determine migration steps. Use when migrating an existing Android codebase from the old, legacy GMA SDK to GMA Next-Gen SDK.

Read: `library/ads/google-mobile-ads-android-migrate-to-next-gen/INSTRUCTIONS.md`

## google-mobile-ads-banner
Provides instructions to implement, integrate, or configure Google Mobile Ads (GMA) banner ads in Android, iOS, or Unity mobile applications. Use when the task involves setting up banner ads in a mobile application. Don't use for other ad formats like interstitial or rewarded ads.

Read: `library/ads/google-mobile-ads-banner/INSTRUCTIONS.md`

## google-mobile-ads-get-started
Provides instructions for integrating the Google Mobile Ads (GMA) SDK. Use this skill when the user wants to get started with, install, integrate, set up, or configure the SDK for AdMob or Ad Manager, GMA Next-Gen SDK or mobile ads framework in an Android, iOS, or Unity application.

Read: `library/ads/google-mobile-ads-get-started/INSTRUCTIONS.md`

## google-mobile-ads-interstitial
Provides instructions for implementing, integrating, or configuring Google Mobile Ads (GMA) SDK interstitial ads in Android, iOS, or Unity mobile applications. Use when the task involves setting up interstitial ads. Don't use for "rewarded interstitial" ads.

Read: `library/ads/google-mobile-ads-interstitial/INSTRUCTIONS.md`

## google-mobile-ads-rewarded
Provides instructions for implementing, integrating, or configuring Google Mobile Ads (GMA) SDK rewarded ads in Android, iOS, or Unity mobile applications. Use when the task involves setting up rewarded ads. Don't use for "rewarded interstitial" ads.

Read: `library/ads/google-mobile-ads-rewarded/INSTRUCTIONS.md`

## google-mobile-ads-validate
Validates a project's Google Mobile Ads (GMA) SDK integration for iOS, Android, or Unity projects. Use when conducting a full pre-launch audit of an app that integrates GMA SDK or when validating any individual GMA SDK integration checks, such as when validating ad unit IDs and ad formats, SKAdNetwork IDs, mediation adapter SDK version compatibility, or ad preloading.

Read: `library/ads/google-mobile-ads-validate/INSTRUCTIONS.md`

## ima-dai-sdk
Integrates the Google Interactive Media Ads (IMA) Dynamic Ad Insertion (DAI) SDK into websites, web apps, mobile apps, or TV apps. Use when: - A video player needs to load and play HLS or DASH streams in web apps, Android apps, iOS apps, tvOS apps, Cast (CAF) receivers, or Roku channels. - The app needs to make use of a Google DAI livestream event asset key, or content source CMS ID, video ID for video on demand. Don't use this skill to load and play a VAST or VMAP URL.

Read: `library/ads/ima-dai-sdk/INSTRUCTIONS.md`

## ima-sdk-client-side
Supports Interactive Media Ads (IMA) SDK. Use this skill for client-side ad insertion when you are requesting video ads for websites, apps, TVs or other platforms using VAST or VMAP. Do not use for Dynamic Ad Insertion (DAI), SSAI, or SGAI.

Read: `library/ads/ima-sdk-client-side/INSTRUCTIONS.md`
