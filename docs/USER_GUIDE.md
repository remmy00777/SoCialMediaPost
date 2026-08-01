# User Guide

## Normal workflow

1. Review the dashboard and platform health.
2. Run or wait for trend discovery.
3. Inspect source labels, limitations, scores, confidence, and evidence.
4. Review generated content concepts and rejected candidates.
5. Preview each platform-specific video and metadata package.
6. Inspect originality, copyright, policy, quality, and media reports.
7. Edit or regenerate individual components when a configured provider supports it.
8. Approve, reject, schedule, export, or publish.
9. Review official post analytics at configured intervals.
10. Evaluate experiments against watch time, completion, shares, saves, comments, follows, negative feedback, and safety guardrails.

Use **Pause All Automation** whenever account behavior, content quality, rights, or provider health is uncertain.

## Multiple social-media accounts

Open **Connected Accounts** and select **Connect another account** for YouTube, TikTok, or Instagram. One application login can store several authorized platform accounts. Each account keeps a separate encrypted OAuth credential, connection status, permissions, quota status, publishing eligibility, and analytics eligibility. When publishing through the API, pass `platform_account_id` to select the destination account.

The application connects existing platform accounts. It does not automatically create new YouTube, TikTok, Instagram, Google, or Meta identities.

## Authorized clip remix

Open **Trend Detail** and upload a source video under **Authorized Clip Remix**. The upload is accepted only when you record one of these rights bases:

- You own the media.
- You have a license permitting full reuse.
- The media is in the public domain.
- The rights owner gave explicit permission.

Licensed, permission-based, and public-domain uploads require a supporting reference. The generator creates an original synthesized voiceover introduction, displays that introduction first, and then plays the complete uploaded clip. The application never downloads a third party's video from a social-media URL.

## Permanent deletion

The content-library pages display the approximate storage used by each package. Select **Delete permanently**, then type `DELETE`. The application removes generated videos, previews, thumbnails, subtitles, ready-to-post mirrors, dependent publication records, quality records, and the package record. The operation cannot be undone.

Deleting a local package does not remove a post that has already been published on TikTok, Instagram, or YouTube. Remove the remote post separately through the platform or an eligible official API.
