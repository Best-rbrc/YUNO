# frontend/ – Web Interface for Yuno

This folder contains the web-based user interface for viewing, managing, and interacting with the person database. The frontend provides an elegant, modern interface for browsing enrolled persons, viewing their context, and managing their information.

---

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [File Structure](#file-structure)
4. [Features](#features)
5. [Architecture](#architecture)
6. [Setup & Configuration](#setup--configuration)
7. [Supabase Integration](#supabase-integration)
8. [UI/UX Design](#uiux-design)
9. [API Integration](#api-integration)
---

## Overview

The Yuno frontend is a **single-page application (SPA)** built with vanilla JavaScript and modern CSS. It connects directly to Supabase to fetch person data and display it in an interactive, card-based interface. The application features a beautiful landing page, animated dashboard, and detailed person modals with full CRUD capabilities.

**Key Characteristics**:
- **Zero build process**: Pure HTML, CSS, and JavaScript
- **Framework-free**: No React, Vue, or Angular - just vanilla JS
- **Supabase-powered**: Direct database and storage integration
- **Responsive design**: Works on mobile, tablet, and desktop
- **Modern aesthetics**: Gradient backgrounds, smooth animations, glassmorphism effects

---

## Technology Stack

### Core Technologies

#### **HTML5**
- Single `index.html` file containing the entire application
- Semantic HTML structure
- SEO-friendly meta tags
- Accessibility considerations

#### **CSS3**
- **Modern Features**:
  - CSS Grid for responsive layouts
  - Flexbox for component alignment
  - CSS Variables for theming (could be added)
  - Animations and transitions
  - Backdrop filters (glassmorphism)
  - Custom scrollbar styling
  
- **Design Techniques**:
  - Gradient backgrounds
  - Card-based layouts
  - Modal overlays
  - Hover effects and micro-interactions
  - Responsive breakpoints

#### **Vanilla JavaScript (ES6+)**
- **Modern JS Features**:
  - Async/await for asynchronous operations
  - Arrow functions
  - Template literals
  - Destructuring
  - Array methods (map, filter, reduce)
  - Promise-based API calls

- **DOM Manipulation**:
  - Direct element creation and updates
  - Event listeners
  - Dynamic content injection
  - State management (via global variables)

### External Libraries

#### **Supabase JavaScript Client (`@supabase/supabase-js@2`)**
- **CDN-loaded**: `https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2`
- **Features Used**:
  - Database queries (SELECT, UPDATE, DELETE)
  - Storage operations (createSignedUrl, download)
  - Client initialization with anon key
  - Real-time subscriptions (could be added)

**Why Supabase?**
- PostgreSQL database with REST API
- Built-in authentication (not yet used)
- File storage with access control
- Real-time capabilities
- Row Level Security (RLS)

---

## File Structure

```
frontend/
├── index.html              # Main application file (all-in-one)
├── SUPABASE_SETUP.md      # Storage bucket configuration guide
└── README.md              # This file
```

## Features

### Landing Page

**Visual Design**:
- Full-screen gradient background (purple to pink)
- Large "YUNO" logo with glow effect
- Tagline: "Smart Person Recognition & Database"
- Animated "Enter Dashboard" button
- Pulsing radial gradients
- Fade-in animations

**Interactions**:
- Single button to enter the dashboard
- Smooth transition to dashboard (fade out effect)

**CSS Effects**:
- `@keyframes pulse`: Pulsing background gradients
- `@keyframes fadeInUp`: Entrance animation
- `@keyframes glow`: Logo glow effect
- Glassmorphism button with hover effects

---

### Dashboard

**Layout**:
- **Header Section**:
  - "Your People" title with gradient text
  - Subtitle with usage instructions
  - Statistics cards (total persons, total memories)
  - Decorative pulsing gradient orb
  
- **Grid Section**:
  - Responsive grid layout (1-3 columns based on screen size)
  - Person cards with hover effects
  - Loading spinner during data fetch
  - Error messages for failed operations

**Statistics**:
- **Total Persons**: Count of enrolled people
- **Total Memories**: Count of persons with context
- **Animated Counters**: Numbers count up from 0 on load

**Responsive Design**:
- Desktop: 3 columns (1400px max width)
- Tablet: 2 columns
- Mobile: 1 column

---

### Person Cards

**Card Structure**:
- **Image Section**: 300px height container
  - Profile photo (or placeholder)
  - Hover zoom effect on image
  
- **Content Section**:
  - Person name (bold, large font)
  - Person ID (smaller, gray text)
  - Context preview (3-line clamp with ellipsis)

**Visual Effects**:
- Border glow on hover
- Elevation increase (translateY + scale)
- Gradient overlay fade-in
- Shadow enhancement
- Smooth 300ms transitions

**Interactions**:
- Click to open detailed modal
- Entire card is clickable

---

###  Person Details Modal

**Structure**:

1. **Header**:
   - Circular profile photo (150px, bordered)
   - Person name (gradient text)
   - Person ID and creation date
   - Close button (top-right)

2. **Body**:
   - **View Mode**:
     - "Context & Information" section
     - Formatted context entries with timestamps
     - Labeled sections (Analyse, Transkript, etc.)
     - Structured display with entry cards
   
   - **Edit Mode**:
     - Name input field
     - Context textarea (expandable)
     - Form validation
   
   - **Delete Confirmation Mode**:
     - Warning message
     - Confirm/Cancel buttons
     - Styled alert box

3. **Footer Actions**:
   - **View Mode**: Edit, Delete buttons
   - **Edit Mode**: Save, Cancel buttons
   - **Delete Mode**: Yes Delete, Cancel buttons

**Features**:
- **Context Parsing**: Intelligently formats context into labeled entries
- **Timestamp Display**: Shows when each context entry was added
- **Multi-line Context**: Preserves newlines and formatting
- **Responsive**: Adapts to mobile screens
- **Keyboard Support**: Close with Escape key
- **Click Outside**: Close by clicking overlay

**Modal Interactions**:
```javascript
openModal(person)      // Open with person data
closeModal()           // Close modal
toggleEdit()           // Switch to edit mode
savePerson()           // Update database
showDeleteConfirmation() // Show delete prompt
confirmDelete()        // Execute deletion
```

---

### CRUD Operations

#### **Create** (Not in Frontend)
- Person creation handled by backend (enroll pipeline)
- Frontend is read-only for new persons

#### **Read**
```javascript
async function fetchPersons() {
  const { data: persons, error } = await supabase
    .from('persons')
    .select('*');
  
  // Process and display persons
}
```

**Process**:
1. Query Supabase `persons` table
2. Fetch all columns (`SELECT *`)
3. Generate signed URLs for images
4. Render person cards
5. Update statistics

#### **Update**
```javascript
async function savePerson() {
  const { data, error } = await supabase
    .from('persons')
    .update({
      name: newName,
      context: newContext
    })
    .eq('id', currentPersonData.id)
    .select();
  
  // Refresh UI
}
```

**Process**:
1. Validate input (name not empty)
2. Update Supabase record
3. Update local state
4. Refresh dashboard grid
5. Show success message

#### **Delete**
```javascript
async function confirmDelete() {
  const { error } = await supabase
    .from('persons')
    .delete()
    .eq('id', currentPersonData.id);
  
  // Refresh UI
}
```

**Process**:
1. Show confirmation dialog
2. Execute DELETE query on confirmation
3. Close modal
4. Remove card from grid
5. Update statistics
6. Show success message

---

## Architecture

### Application Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        Landing Page                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  "YUNO" Logo + "Enter Dashboard" Button               │  │
│  └────────────────────────┬─────────────────────────────┘  │
└────────────────────────────┼────────────────────────────────┘
                             │ Click
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                          Dashboard                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Header: Title, Subtitle, Stats                       │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  Loading State → Fetch from Supabase                 │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  Person Cards Grid (Generated Dynamically)            │  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐                 │  │
│  │  │ Card 1 │  │ Card 2 │  │ Card 3 │                 │  │
│  │  └───┬────┘  └────────┘  └────────┘                 │  │
│  └──────┼───────────────────────────────────────────────┘  │
└─────────┼──────────────────────────────────────────────────┘
          │ Click Card
          ▼
┌─────────────────────────────────────────────────────────────┐
│                      Person Details Modal                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Photo + Name + ID + Created Date                     │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  ┌─ View Mode ─────────────────────────────────────┐ │  │
│  │  │  Context Entries (formatted with timestamps)     │ │  │
│  │  │  [Edit] [Delete]                                 │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  │                        OR                              │  │
│  │  ┌─ Edit Mode ─────────────────────────────────────┐ │  │
│  │  │  Name Input                                       │ │  │
│  │  │  Context Textarea                                 │ │  │
│  │  │  [Save] [Cancel]                                  │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  │                        OR                              │  │
│  │  ┌─ Delete Confirmation ───────────────────────────┐ │  │
│  │  │  "Are you sure?"                                  │ │  │
│  │  │  [Yes, Delete] [Cancel]                           │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Frontend                    Supabase                  Backend
   │                           │                         │
   ├─ Initial Load ───────────►│                         │
   │                           │                         │
   │◄─ Fetch Persons ──────────┤                         │
   │   (SELECT * FROM persons) │                         │
   │                           │                         │
   ├─ Get Image URLs ─────────►│                         │
   │   (createSignedUrl)       │                         │
   │                           │                         │
   │◄─ Signed URLs ────────────┤                         │
   │                           │                         │
   │                           │                         │
   ├─ User Updates Person ────►│                         │
   │   (UPDATE persons)        │                         │
   │                           │                         │
   │◄─ Success ────────────────┤                         │
   │                           │                         │
   │                           │                         │
   │                           │   Backend writes to DB  │
   │                           │◄────────────────────────┤
   │                           │   (sync_manager.py)     │
   │                           │                         │
   ├─ Periodic Refresh ───────►│                         │
   │   (re-fetch persons)      │                         │
   │                           │                         │
```

### State Management

**Global Variables**:
```javascript
const supabase = window.supabase.createClient(URL, KEY);
let currentPersonData = null; // Currently selected person in modal
```

**Component State**:
- Landing page visibility: DOM manipulation (`display: none/block`)
- Dashboard visibility: CSS class (`active`)
- Modal state: CSS class (`active`)
- Edit mode: Form visibility toggles
- Delete confirmation: Element visibility toggles

**No Framework State Management**:
- Direct DOM manipulation
- Event-driven updates
- No virtual DOM or reactive state

---

## Setup & Configuration

### Prerequisites

1. **Supabase Project**:
   - Active Supabase account
   - Project created with `persons` table
   - Storage buckets configured

2. **Web Server** (for local testing):
   - Python: `python -m http.server 8000`
   - Node.js: `npx serve`
   - VS Code: Live Server extension

### Configuration Steps

#### 1. Update Supabase Credentials

**Location**: `index.html` (inside `<script>` tag)

```javascript
// Configuration
const SUPABASE_URL = 'https://YOUR-PROJECT.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGc...YOUR_ANON_KEY';
```

**How to Get Credentials**:
1. Go to Supabase Dashboard
2. Select your project
3. Navigate to **Settings** → **API**
4. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon/public key** → `SUPABASE_ANON_KEY`

#### 2. Configure Storage Buckets

**Required Buckets**:
- `persons-photos`: For profile images
- `persons-audio` (optional): For audio recordings

**Configuration**:
See `SUPABASE_SETUP.md` for detailed instructions on:
- Creating buckets
- Setting privacy levels
- Configuring RLS policies
- Generating signed URLs

**Quick Setup**:
```sql
-- Create storage buckets (via Supabase Dashboard → Storage)
-- Bucket name: persons-photos
-- Public: No (private)

-- Create RLS policy for anon access
CREATE POLICY "Allow anon to read photos"
ON storage.objects FOR SELECT
TO anon
USING (bucket_id = 'persons-photos');
```

#### 3. Database Schema

**Required Table**: `persons`

```sql
CREATE TABLE persons (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name TEXT,
  context TEXT,
  photo_url TEXT,          -- URL to Supabase storage
  photo_path TEXT,         -- Local file path (for backend)
  audio_url TEXT,          -- URL to audio storage
  audio_path TEXT,         -- Local audio path
  embedding BYTEA,         -- Face embedding (hex-encoded)
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster queries
CREATE INDEX idx_persons_name ON persons(name);
CREATE INDEX idx_persons_created_at ON persons(created_at DESC);
```

#### 4. Row Level Security (RLS)

**Enable RLS**:
```sql
ALTER TABLE persons ENABLE ROW LEVEL SECURITY;
```

**Create Policies**:
```sql
-- Allow anonymous users to read all persons
CREATE POLICY "Allow anon read access"
ON persons FOR SELECT
TO anon
USING (true);

-- Allow authenticated users to update
CREATE POLICY "Allow authenticated update"
ON persons FOR UPDATE
TO authenticated
USING (true);

-- Allow authenticated users to delete
CREATE POLICY "Allow authenticated delete"
ON persons FOR DELETE
TO authenticated
USING (true);
```

**Note**: Currently, the frontend uses `anon` key for all operations. For production, implement proper authentication and restrict policies to authenticated users only.

---

## Supabase Integration

### Client Initialization

```javascript
// Initialize Supabase client (CDN-loaded library)
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
```

**CDN Source**:
```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
```

### Database Queries

#### **Fetch All Persons**
```javascript
const { data: persons, error } = await supabase
  .from('persons')
  .select('*');
```

**Returns**:
```javascript
[
  {
    id: 1,
    name: "Max Mustermann",
    context: "Analyse: ...\nTranskript: ...",
    photo_url: "https://...supabase.co/storage/v1/object/public/persons-photos/...",
    photo_path: "data/persons/person_1_MaxMustermann/profile.jpg",
    embedding: "\\x0a1b2c...",
    created_at: "2025-01-15T10:30:00Z",
    updated_at: "2025-01-15T10:30:00Z"
  },
  // ...
]
```

#### **Update Person**
```javascript
const { data, error } = await supabase
  .from('persons')
  .update({
    name: "New Name",
    context: "Updated context"
  })
  .eq('id', personId)
  .select(); // Return updated row
```

#### **Delete Person**
```javascript
const { error } = await supabase
  .from('persons')
  .delete()
  .eq('id', personId);
```

### Storage Operations

#### **Generate Signed URL**
```javascript
const { data, error } = await supabase.storage
  .from('persons-photos')
  .createSignedUrl(filePath, 3600); // 1 hour expiry

const signedUrl = data.signedUrl;
```

**Why Signed URLs?**
- Work with private buckets
- Provide temporary access
- Don't expose sensitive URLs
- Can be revoked

**Expiry**: 3600 seconds (1 hour)

#### **Download File**
```javascript
const { data, error } = await supabase.storage
  .from('persons-photos')
  .download(filePath);

// data is a Blob
const objectUrl = URL.createObjectURL(data);
```

### Error Handling

```javascript
try {
  const { data, error } = await supabase
    .from('persons')
    .select('*');
  
  if (error) {
    throw new Error(`Database error: ${error.message}`);
  }
  
  // Process data
} catch (error) {
  console.error('Error fetching persons:', error);
  displayErrorMessage(error.message);
}
```

**Common Errors**:
- `FetchError`: Network issues
- `PostgrestError`: Database query errors
- `StorageError`: File access issues
- Authentication errors (if RLS policies block access)

---

## UI/UX Design

### Design System

#### **Color Palette**
```css
/* Primary Colors (Gradients) */
--primary-purple: #667eea;
--primary-pink: #764ba2;
--primary-light: #f093fb;

/* Backgrounds */
--bg-dark: #0a0a0a;
--bg-medium: #1a1a2e;

/* Text */
--text-white: #ffffff;
--text-gray-light: rgba(255,255,255,0.7);
--text-gray-medium: rgba(255,255,255,0.5);

/* Accents */
--accent-green: #4caf50;
--accent-red: #ff4d4d;
--accent-blue: #667eea;
```

#### **Typography**
```css
/* Font Stack */
font-family: -apple-system, BlinkMacSystemFont, 
             'Segoe UI', 'Inter', Roboto, Oxygen, 
             Ubuntu, Cantarell, sans-serif;

/* Font Sizes */
--font-size-hero: 8rem;        /* Landing logo */
--font-size-title: 3.5rem;     /* Dashboard title */
--font-size-heading: 2.5rem;   /* Modal name */
--font-size-card: 1.5rem;      /* Card names */
--font-size-body: 1rem;        /* Body text */
--font-size-small: 0.85rem;    /* Metadata */
```

#### **Spacing**
```css
/* Padding/Margin Scale */
--space-xs: 0.5rem;   /* 8px */
--space-sm: 1rem;     /* 16px */
--space-md: 1.5rem;   /* 24px */
--space-lg: 2rem;     /* 32px */
--space-xl: 3rem;     /* 48px */
--space-2xl: 4rem;    /* 64px */
```

#### **Border Radius**
```css
--radius-sm: 8px;      /* Buttons */
--radius-md: 12px;     /* Cards */
--radius-lg: 20px;     /* Person cards */
--radius-xl: 24px;     /* Modal */
--radius-full: 9999px; /* Pills/circles */
```

### Animations

#### **Landing Page Animations**
```css
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes glow {
  from { filter: drop-shadow(0 0 20px rgba(255,255,255,0.3)); }
  to { filter: drop-shadow(0 0 40px rgba(255,255,255,0.5)); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}
```

#### **Dashboard Animations**
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(50px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes float {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

#### **Hover Transitions**
```css
/* Person Cards */
.person-card {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.person-card:hover {
  transform: translateY(-10px) scale(1.02);
  box-shadow: 0 20px 60px rgba(102,126,234,0.3);
}

/* Buttons */
.modal-button {
  transition: all 0.3s ease;
}

.modal-button:hover {
  transform: translateY(-2px);
}
```

### Glassmorphism Effects

```css
.sign-in-button {
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  border: 2px solid rgba(255, 255, 255, 0.3);
}

.person-card {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
```

### Responsive Design

#### **Breakpoints**
```css
/* Mobile: < 768px (default) */
/* Tablet: 768px - 1024px */
/* Desktop: > 1024px */

@media (max-width: 768px) {
  .yuno-logo { font-size: 5rem; }
  .persons-grid { grid-template-columns: 1fr; }
  .dashboard-title { font-size: 2.5rem; }
}
```

#### **Grid Layouts**
```css
/* Desktop: 3 columns */
.persons-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 2rem;
}

/* Tablet: 2 columns (automatic via minmax) */
/* Mobile: 1 column (forced via media query) */
```

---

## API Integration

### Image Loading Strategy

The frontend uses a sophisticated multi-fallback image loading strategy:

#### **1. Primary: Supabase Signed URLs**
```javascript
async function getImageUrl(photoUrl) {
  const storageInfo = extractStoragePath(photoUrl);
  
  const { data, error } = await supabase.storage
    .from(storageInfo.bucket)
    .createSignedUrl(storageInfo.path, 3600);
  
  return data.signedUrl;
}
```

**Process**:
1. Parse photo URL to extract bucket and path
2. Generate signed URL with 1-hour expiry
3. Return temporary URL for image tag

#### **2. Fallback: Direct URL**
```javascript
if (photoUrl.startsWith('http://') || photoUrl.startsWith('https://')) {
  return photoUrl; // Use URL directly
}
```

**Used for**:
- Public buckets
- External image URLs
- Legacy data

#### **3. Final Fallback: UI Avatars**
```javascript
const placeholderUrl = `https://ui-avatars.com/api/` +
  `?name=${encodeURIComponent(name)}` +
  `&size=200` +
  `&background=667eea` +
  `&color=fff` +
  `&bold=true`;
```

**Features**:
- Generates avatar from name initials
- Custom colors matching theme
- Always works (external service)

#### **Error Handling**
```javascript
<img 
  src={imageUrl}
  onError={(e) => {
    if (!e.target.src.includes('ui-avatars.com')) {
      // Retry with cache busting
      e.target.src = imageUrl + '?_t=' + Date.now();
      e.target.dataset.retried = 'true';
    } else {
      // Final fallback
      e.target.src = placeholderUrl;
    }
  }}
/>
```

### Context Formatting

The frontend intelligently parses and formats person context:

#### **Context Structure**
```
Analyse: Max ist ein Kommilitone aus dem HCI Kurs
Interesse: UI/UX Design, Programmierung

Transkript: Hallo, ich bin Max. Ich studiere Informatik...
```

#### **Parsing Logic**
```javascript
function renderContextEntries(person) {
  const raw = person.context || '';
  const blocks = raw.split(/\n\n+/); // Split on double newlines
  
  // Group by labels (Analyse:, Transkript:, etc.)
  const entries = [];
  let buffer = [];
  
  for (const part of blocks) {
    if (/^(Analyse:|Transkript:)/i.test(part) && buffer.length > 0) {
      entries.push(buffer.join('\n\n'));
      buffer = [part];
    } else {
      buffer.push(part);
    }
  }
  
  // Render as separate entry cards
  return entries.map((text, idx) => {
    const title = extractLabel(text); // "Analyse" or "Transkript"
    const body = removeLabel(text);
    const timestamp = formatTimestamp(person.updated_at);
    
    return `
      <div class="context-entry">
        <div class="context-entry-header">
          <div class="context-entry-title">${title}</div>
          <div class="context-entry-meta">${timestamp}</div>
        </div>
        <div class="context-entry-body">${body}</div>
      </div>
    `;
  }).join('');
}
```

#### **Rendered Output**
```html
<div class="context-entry">
  <div class="context-entry-header">
    <div class="context-entry-title">Analyse</div>
    <div class="context-entry-meta">15.01.2025, 10:30</div>
  </div>
  <div class="context-entry-body">
    Max ist ein Kommilitone aus dem HCI Kurs...
  </div>
</div>
```
