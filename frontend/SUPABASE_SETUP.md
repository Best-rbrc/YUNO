# Setting Up Private Buckets in Supabase

This guide explains how to set your `person-photos` bucket to private while still allowing your frontend to access images.

## Step 1: Make the Bucket Private

1. Go to your Supabase dashboard: https://supabase.com/dashboard
2. Select your project
3. Go to **Storage** in the left sidebar
4. Find your `person-photos` bucket (and `person-audio` if you have one)
5. Click on the bucket name
6. In the bucket settings, find **Public bucket** toggle
7. **Turn OFF** the "Public bucket" toggle (make it private)

## Step 2: Set Up Storage Policies

Even though the bucket is private, you need to allow the `anon` role (your frontend) to read files. This is done through Storage Policies.

1. Still in the Storage section, click on your bucket (`person-photos`)
2. Click on the **Policies** tab
3. You'll see "No policies created yet" - click **New Policy**
4. Choose **For full customization** (or use a template)

### Policy for Reading Files (SELECT)

Create a policy that allows the anon role to download/read files:

**Policy Name:** `Allow anon to read photos`

**Allowed Operation:** SELECT (read/download)

**Policy definition:** Use this SQL:

```sql
(bucket_id = 'person-photos'::text)
```

**WITH CHECK:** (leave empty or same as above)

**USING expression:** Use this SQL:

```sql
auth.role() = 'anon'
```

OR, if you want even more control (only allow authenticated users):

```sql
true
```

The `true` policy will allow anyone with the anon key to read files, which is what you need for your frontend to work.

### Alternative: Using RLS Policy Helper

If Supabase has a policy helper:

1. Select **"SELECT"** as the operation
2. Select **"anon"** as the role
3. Check **"WITH CHECK"** and set it to `true`
4. Save the policy

## Step 3: Verify It Works

1. Make sure your bucket's "Public bucket" toggle is **OFF** (private)
2. Your frontend should still work because:
   - The signed URLs are generated using your anon key
   - The storage policy allows `anon` role to SELECT (read) files
   - The frontend uses `createSignedUrl()` which works with private buckets and proper policies

## Step 4: Do the Same for Audio Bucket (if needed)

If you have a `person-audio` bucket:
1. Repeat the same steps
2. Create a policy for `person-audio` bucket
3. Use the same policy structure

## Security Notes

- **Private buckets are more secure** - files can't be accessed without proper authentication
- **Signed URLs expire** - in the code, they expire after 1 hour (3600 seconds)
- **RLS policies control access** - even with signed URLs, the policy must allow the operation
- **Anon key is public** - anyone can see it in your frontend code, so policies are important

## Troubleshooting

If images don't load after making the bucket private:

1. Check that the policy was created correctly
2. Verify the policy allows `anon` role
3. Check browser console for error messages
4. Make sure the bucket name matches exactly: `person-photos`
5. Verify your anon key is correct in the frontend code

The frontend code already handles private buckets correctly by using `createSignedUrl()` when it detects a non-public bucket.

