# SPEC.md

> For technical implementation details, architecture, and developer documentation, see [AGENTS.md](./AGENTS.md).

---

## Table of Contents

- [Overview](#overview)
- [Users & Roles](#users--roles)
- [Business Rules](#business-rules)
  - [Rating Rules](#rating-rules)
  - [Movie Data Rules](#movie-data-rules)
  - [Ranking Algorithm](#ranking-algorithm)
  - [User Permissions](#user-permissions)
- [Features](#features)
  - [Movie Discovery & Browsing](#feature-movie-discovery--browsing)
  - [Swipe Rating Interface](#feature-swipe-rating-interface)
  - [Team Rankings & Statistics](#feature-team-rankings--statistics)
  - [User Profiles](#feature-user-profiles)
  - [Taste Comparison](#feature-taste-comparison)
  - [Movie Addition via IMDB](#feature-movie-addition-via-imdb)
  - [Social Authentication](#feature-social-authentication)
- [User Flows](#user-flows)
  - [Flow 1: New User Onboarding](#flow-1-new-user-onboarding)
  - [Flow 2: Rating Movies via Swipe Interface](#flow-2-rating-movies-via-swipe-interface)
  - [Flow 3: Adding a New Movie](#flow-3-adding-a-new-movie)
  - [Flow 4: Comparing Tastes](#flow-4-comparing-tastes)
- [Out of Scope](#out-of-scope)
- [Open Questions](#open-questions)

---

## Overview

**PopQuiz** is a collaborative voting platform for teams to discover and rank their favorite pop culture items — currently Movies and TV Shows.

**What is it?**
A web application that transforms pop culture discussions into an interactive, data-driven experience. Team members rate items using a Tinder-style swipe interface, and the app aggregates votes to reveal team rankings, identify taste compatibility between members, and surface items that spark debate.

**Problem it Solves:**
- **Decision Paralysis:** Groups struggle to choose movies everyone will enjoy
- **Unknown Preferences:** Teams don't know what movies colleagues have seen or liked
- **Conversation Starters:** Difficult to discover shared interests or interesting disagreements
- **Manual Tracking:** No easy way to track and compare movie preferences across a group

**Core Value Proposition:**
Turn subjective movie opinions into objective data that reveals patterns, compatibility, and consensus within your team.

**Target Audience:**
- Friend groups planning movie nights or TV watch parties
- Work teams building social connections
- Film clubs discussing cinema
- Any group of 3-20 people who enjoy pop culture together

**Primary Goals:**
1. Make rating movies fast and fun (swipe interface)
2. Reveal team consensus through fair rankings
3. Enable taste compatibility comparisons
4. Spark conversations about movies

**Key Success Metrics:**
- Average ratings per user (target: 50+)
- User engagement (daily active users)
- Completion rate on swipe voting sessions
- Social features usage (profile views, comparisons)

---

## Users & Roles

PopQuiz has a flat permission model - all authenticated users have equal access to features. There are no formal admin or moderator roles beyond the Django admin interface.

### Team Member (Standard User)

**Description:** Any registered user participating in the team's movie rating activity.

**Key Characteristics:**
- Movie enthusiasts who want to share opinions
- Interested in discovering team preferences
- May have seen varying numbers of movies (from casual viewers to cinephiles)
- Motivated by curiosity about teammates' tastes

**Primary Goals:**
- Rate movies they've seen
- Discover what the team collectively likes/dislikes
- Find out which teammates have similar tastes
- See recommendations based on team ratings

**Can Do:**
- Rate any movie with 5-point scale (Loved, Liked, Okay, Disliked, Hated, Haven't Seen)
- Add new movies via IMDB link
- View own profile with rating history
- View other users' profiles
- Compare taste with other users (2-way or 3-way)
- Browse movies by category
- View team rankings and statistics
- Sort and filter their own ratings

**Cannot Do:**
- Delete other users' ratings
- Modify system settings
- Access admin panel
- Delete categories or movies
- Remove other users' added movies

**Typical Persona:**
"Jamie, 32, works in marketing, watches 2-3 movies per month, curious about what movies the team has seen and wants to find commonalities with coworkers for better conversations."

### Guest/Logged-Out Visitor

**Description:** Non-authenticated visitors who can browse limited public information.

**Can See:**
- Homepage with basic information
- Login/registration options
- Partial user information (first name + last initial only)

**Cannot Access:**
- Rating functionality
- Full user profiles
- Team member lists
- Comparison features
- Movie addition

**Purpose:**
Provides preview of the app while protecting team privacy. Encourages registration to access features.

---

## Business Rules

### Rating Rules

**Rating Scale:**
- **5-point Likert scale** with emoji representation and numeric values:
  - 🤩 Loved (+2) - Absolute favorite, would watch again
  - 🙂 Liked (+1) - Enjoyed it, glad I watched
  - 😐 Okay (0) - Neutral, neither good nor bad
  - 😕 Disliked (-1) - Didn't enjoy, wouldn't recommend
  - 😡 Hated (-2) - Strongly disliked, regret watching
  - ⏭️ Haven't Seen (no numeric value) - Haven't watched yet

**Rating Constraints:**
- Each user can rate each movie **exactly once**
- Changing a rating updates the existing record (no duplicates)
- "Haven't Seen" is not counted in ranking calculations
- Users cannot rate a movie without being logged in
- Ratings persist indefinitely (no expiration)

**Rating Display:**
- Scale always displayed left-to-right: Hated → Disliked → Okay → Liked → Loved
- "Haven't Seen" visually separated from the rating scale (on the right)
- Color coding: Red (Hated), Orange (Disliked), Yellow (Okay), Green (Liked), Purple (Loved), Gray (Haven't Seen)
- Emoji size varies by context (text-lg to text-4xl) for better visibility

**Rating Privacy:**
- All team members can see who rated what
- Logged-out visitors cannot see ratings
- Individual ratings shown on movie detail pages
- Aggregate statistics shown on ranking pages

### Movie Data Rules

**IMDB Integration:**
- Items must have a valid IMDB ID (ttXXXXXXX format)
- Each IMDB ID can only be added once (uniqueness enforced)
- Item metadata automatically fetched from IMDB:
  - Title (English version prioritized)
  - Year of release
  - Director
  - Genres (up to 3, comma-separated)
  - Poster image — downloaded and cached locally on the server
  - IMDB URL for reference

**Poster Image Caching:**
- Poster images are downloaded from Amazon CDN at item-creation time
- Stored locally at `/media/posters/<imdb_id>.jpg` and served from the app's own domain
- Eliminates repeated external CDN requests on every page load
- If download fails at creation time, external URL is used as fallback
- Backfill existing items with: `uv run python manage.py download_posters`

**Item Addition:**
- Any authenticated user can add items
- Must provide IMDB URL or IMDB ID
- System tracks who added each item (`added_by` field)
- Items without an `added_by` user shown as "Added by Claude" (programmatic imports)
- Duplicate IMDB IDs rejected with error message

**Title Cleaning:**
- Automatic removal of IMDB metadata from titles:
  - Star ratings (⭐ 7.9) stripped
  - Genre suffixes after pipe (| Animation, Comedy) removed
  - Years in parentheses (2023) removed
  - HTML entities decoded (&amp; → &)

**Item Categorization:**
- Items belong to categories (e.g., "Movies", "TV Shows")
- Categories have slugs for URL routing
- Items can only belong to one category
- New categories are created via the Django admin; no user-facing category creation

### Ranking Algorithm

**Simple Average Method:**
- Ranking based on **arithmetic mean** of all ratings for a movie
- Formula: `average = sum(rating_values) / count(ratings)`
- Display score: Convert -2 to +2 range → 0 to 100 scale
  - `display_score = ((average + 2) / 4) * 100`

**Score Calculation Example:**
- Movie with ratings: Loved (+2), Liked (+1), Liked (+1), Okay (0)
- Sum: 2 + 1 + 1 + 0 = 4
- Count: 4 ratings
- Average: 4 / 4 = 1.0
- Display: ((1.0 + 2) / 4) * 100 = 75

**Ranking Rules:**
- Movies with **zero ratings** get score of 0 (appear at bottom)
- "Haven't Seen" ratings **excluded** from calculations
- All ratings weighted equally (no time decay or weighting)
- Ties broken alphabetically by title
- Rankings recalculated on every page load (no caching)

**Statistical Views:**
- **Team Rankings:** All movies ranked by score
- **By Decade:** Movies grouped by release decade, ranked within each decade
- **Eclectic Tastes:** Users ranked by how often they disagree with consensus
- **Divisive Movies:** Movies with most polarized ratings (measured by standard deviation)

### User Permissions

**Authentication Requirements:**
- Registration: Username, email, password (first/last name optional)
- Login: Username or email + password
- Alternative: Slack OAuth (auto-creates account)
- Email verification: **DISABLED** (no SMTP)
- Password reset: **DISABLED** (no SMTP)

**Profile Privacy:**
- Logged-in users: See full names and avatars
- Logged-out users: See first name + last initial only (e.g., "John S.")
- All ratings are public within the team
- No private or hidden ratings

**Access Control:**
- Public pages: Homepage (limited), login, registration
- Protected pages: Rating, profiles, comparisons, movie addition, statistics
- No granular permissions (all authenticated users equal)
- No blocking or privacy controls between team members

---

## Features

### Feature: Movie Discovery & Browsing

**Description:**
Browse all movies in a category with inline rating buttons, search functionality, and filtering options.

**User Value:**
Provides quick overview of available movies, allows at-a-glance rating without navigating to separate pages, and enables discovery of specific movies.

**Functionality:**
- Display all movies in category with poster grid layout
- Show movie title, year, director, genre
- Inline rating buttons below each poster (5 emoji buttons + Haven't Seen)
- Click rating button to instantly save rating (AJAX, no page reload)
- Current user's rating highlighted with colored background
- Movie count displayed ("658 movies")
- Movies clickable to view detailed information
- Responsive grid: 2-10 columns depending on screen size
- Movies sorted by user's rating preference (Loved → Liked → Okay → Disliked → Hated → Haven't Seen → Unrated)

**User Interactions:**
- Scroll through movie grid
- Click emoji button to rate/change rating
- Click movie poster or title → navigate to movie detail page
- Visual feedback on rating (button highlighting)

**Edge Cases:**
- Category with no movies: Show message "No items in this category yet"
- User hasn't rated anything: All buttons appear neutral
- Very long movie titles: Truncate with ellipsis
- Missing posters: Show placeholder or broken image icon

**Success Criteria:**
- Page loads in <3 seconds with 500+ movies
- Rating updates instantly without page reload
- Correct rating highlighted for current user
- Responsive layout works on 320px+ screens

---

### Feature: Swipe Rating Interface

**Description:**
Tinder-style card interface for quickly rating movies one at a time with swipe gestures (mobile) or button clicks (desktop/mobile).

**User Value:**
Makes rating large numbers of movies fast and fun, reduces decision fatigue with focused one-at-a-time presentation, provides sense of progress.

**Functionality:**
- Display one movie at a time with large poster
- Show movie title, year, IMDB link
- Five rating buttons + Haven't Seen button
- Progress bar showing completion (e.g., "47 of 658 rated")
- Percentage indicator
- Immediate transition to next unrated movie after rating
- Random order to prevent alphabetical bias
- Desktop: 2x2 button grid layout
- Mobile: Single row of buttons, compact layout
- Swipe gestures (mobile only):
  - Swipe right >100px → "Loved" rating
  - Swipe left >100px → "Hated" rating
  - Visual feedback overlay (green ✓ or red ✗)
  - Poster animates with swipe
- AJAX submission (no page reloads)
- Fixed layout heights prevent jitter

**User Interactions:**
- Click/tap emoji button to rate
- Swipe poster left/right (mobile)
- Click "Haven't Seen" to skip
- Click IMDB link to open movie info in new tab
- Progress bar shows advancement automatically

**Edge Cases:**
- All movies rated: Show completion message "You've rated all movies!"
- Single unrated movie: Progress shows "657 of 658 rated"
- Failed submission: Show error, don't advance to next movie
- Swipe threshold not met: Poster snaps back to center

**Success Criteria:**
- Rating submission completes in <1 second
- Next movie loads immediately after rating
- Progress bar updates accurately
- Swipe gestures feel natural on mobile
- No layout jitter when movies change
- Works smoothly with 500+ movies

---

### Feature: Team Rankings & Statistics

**Description:**
View movies ranked by team consensus with detailed statistics, breakdowns by decade, eclectic users, and divisive movies.

**User Value:**
Reveals team preferences, sparks discussions, helps choose movies for group viewing, shows interesting patterns in team taste.

**Functionality:**

**Team Rankings Page:**
- All movies ranked from highest to lowest score
- Display: poster, title, year, score (0-100)
- Vote breakdown: Count of each rating type
- Visual progress bars showing rating distribution
- Color-coded by rating (red-orange-yellow-green-purple)
- Clickable movie titles → movie detail page

**By Decade Page:**
- Movies grouped by release decade (2020s, 2010s, etc.)
- Ranked within each decade
- Shows how many movies per decade
- Same vote breakdown and progress bars
- Most recent decades appear first

**Eclectic Tastes Page:**
- Users ranked by how often they disagree with team consensus
- "Eclectic score" = % of disagreements
- Shows up to 5 "contrarian picks" per user (movies they loved/hated vs. team)
- Helps identify unique opinions

**Divisive Movies Page:**
- Movies ranked by polarization (standard deviation of ratings)
- Shows movies that split the team
- Vote breakdown highlighting disagreement
- Identifies movies that spark debate

**User Interactions:**
- Scroll through rankings
- Click movie → view full details
- Click user name → view profile
- View vote breakdown on hover (or tap on mobile)

**Edge Cases:**
- No movies rated yet: Show message "No ratings yet, start voting!"
- Tied scores: Sort alphabetically
- User with no ratings: Don't show in Eclectic list
- Movie with only 1 rating: Shows in rankings but may not be meaningful

**Success Criteria:**
- Rankings load in <2 seconds
- Accurate score calculations
- Vote breakdowns sum to total votes
- Responsive on all screen sizes
- Clear visual hierarchy (best to worst)

---

### Feature: User Profiles

**Description:**
Personalized profile pages showing rating history, statistics, and sorting/filtering options.

**User Value:**
See your own rating history, track what you've rated, organize by director/genre/year, share taste with teammates, get movie recommendations.

**Functionality:**
- Header with user info and avatar (if Slack OAuth)
- Stats bar showing rating distribution (visual segments for each rating type)
- Rating counts: X Loved, X Liked, X Okay, X Disliked, X Hated, X Haven't Seen
- Total ratings cast
- **Category filter tabs:** When a user has ratings in more than one category, tabs appear (e.g., All | Movies | TV Shows). Selecting a tab scopes the entire page — rating grid, unseen items, and background poster collage — to that category. Tabs are always visible regardless of whether the selected category has rated items.
- Item grid with poster, title, rating badge
- Multiple sort options (preserved when switching category tabs):
  - **By Title:** Alphabetical A-Z (default)
  - **By Year:** Chronological (newest first)
  - **By Director:** Group by director name
  - **By Genre:** Group by genre (items can appear multiple times)
  - **By Rating:** Group by user's rating (Loved/Liked/etc.)
  - **By Popularity:** Sort by total team ratings count
- Badge on each poster shows user's rating (emoji)
- Clickable items → item detail page
- "Recommended for You" section: Top 20 unrated items ranked by team (filtered to selected category)

**User Interactions:**
- Click sort button to change view
- Scroll through grouped sections
- Click movie to view details
- Click director/genre name to focus on that group

**Edge Cases:**
- User with no ratings: Show message "No ratings yet" + link to start rating
- Items without director: Appear in "Unknown Director" group
- Items without genre: Appear in "Unknown Genre" group
- User viewing others' profiles: Same layout, but shows "Their" instead of "Your"
- Switching to a category with no rated items: Category tabs remain visible so user can switch back; ratings grid shows empty state

**Success Criteria:**
- Profile loads in <2 seconds with 100+ ratings
- Sort changes apply instantly
- All groupings accurate
- Stats bar percentages correct
- Responsive layout on mobile

---

### Feature: Taste Comparison

**Description:**
Compare movie preferences between 2 or 3 users to discover compatibility and interesting disagreements.

**User Value:**
Identify shared favorites, discover differences, spark conversations, find movie buddies with similar taste.

**Functionality:**

**2-Way Comparison:**
- Venn diagram visualization showing overlap
- Compatibility percentage: % of movies both rated where they agree
- Quick stats: Both Loved, Both Hated, Major Disagreements
- Movie sections:
  - **Both Love:** Movies both rated Loved
  - **Both Hate:** Movies both rated Hated
  - **Disagree:** Movies rated oppositely (one Loved, other Hated)
  - **Only User1 Rated:** Movies only first user has seen
  - **Only User2 Rated:** Movies only second user has seen
- Each section shows movie posters in grid
- Disagreement cards show both users' ratings with emojis

**3-Way Comparison:**
- 3-circle Venn diagram
- Shows 7 regions: 3 solo, 3 two-way overlaps, 1 three-way overlap
- Counts for each region
- Detailed sections below showing movies in each overlap category
- Two-way overlap statistics for each pair

**User Interactions:**
- Select users from dropdown on homepage
- Click "Compare" button
- View Venn diagram and statistics
- Scroll through movie sections
- Click movie → view details
- Click user name → view profile

**Edge Cases:**
- Users with no common movies: Show "No overlap yet, keep rating!"
- Users who haven't rated same movies: Compatibility = 0%
- Selecting same user twice: Show error message
- Three users with no three-way overlap: Venn center shows 0

**Success Criteria:**
- Comparison calculates correctly
- Venn diagram numbers accurate
- Movie lists match diagram regions
- Compatible with 500+ ratings per user
- Mobile-friendly diagram layout

---

### Feature: Item Addition via IMDB

**Description:**
Add new items (movies, TV shows, etc.) to the database by providing an IMDB URL or ID, with automatic metadata fetching and poster caching.

**User Value:**
Expand movie library without manual data entry, ensure accurate information from trusted source, maintain consistent quality.

**Functionality:**
- Form input: IMDB URL or IMDB ID
- Supports both formats:
  - Full URL: `https://www.imdb.com/title/tt0111161/`
  - Just ID: `tt0111161`
- ID extraction via regex
- IMDB page scraping for metadata:
  - Title (English, cleaned)
  - Year
  - Director (first listed if multiple)
  - Genres (up to 3)
  - Poster image — downloaded immediately to `/media/posters/<imdb_id>.jpg`
- Validation:
  - IMDB ID must be valid format
  - Item cannot already exist (duplicate check)
  - IMDB page must load successfully
- Success: Redirect to category page with confirmation message
- Failure: Show error message inline, keep form populated
- Tracks who added the item (`added_by` field)

**User Interactions:**
- Click "Add Movie" button on category page
- Paste IMDB URL or type ID
- Click "Add Movie" submit button
- Wait for fetch (loading indicator)
- Redirected on success
- See new movie in category list

**Edge Cases:**
- Invalid IMDB ID format: Show error "Invalid IMDB ID"
- Duplicate movie: Show error "Movie already exists"
- IMDB page not found (404): Show error "Movie not found on IMDB"
- IMDB changes HTML structure: Scraping fails, show error
- Missing metadata (no director): Store empty string, still create movie
- Network timeout: Show error "Failed to fetch movie data"

**Success Criteria:**
- Successfully adds valid movies
- Prevents duplicates
- Fetches accurate metadata
- Handles errors gracefully
- Provides clear feedback to user
- Completes in <3 seconds for typical movie

---

### Feature: Social Authentication

**Description:**
Sign in using Slack account (OAuth 2.0) with automatic profile sync.

**User Value:**
No need to remember another password, quick signup with work/team Slack account, profile picture and name auto-populated.

**Functionality:**
- "Sign in with Slack" button on login page
- Redirects to Slack OAuth consent page
- User approves permissions: openid, profile, email
- Callback to app with auth token
- App fetches user info from Slack:
  - First name (given_name)
  - Last name (family_name)
  - Email
  - Avatar (192px picture)
- Auto-creates account if doesn't exist
- Updates profile on each login (keeps data fresh)
- Session created, user logged in
- Redirect to homepage

**User Interactions:**
- Click "Sign in with Slack" button
- Approve permissions on Slack page (first time only)
- Redirected back to app, logged in automatically
- See own avatar in navigation bar

**Edge Cases:**
- User denies permissions: Redirect back to login with message
- Slack returns error: Show error page with retry option
- Email already registered: Link accounts or show conflict error
- User changes Slack info: Updates on next login
- Slack API down: Fall back to traditional login

**Success Criteria:**
- Completes full OAuth flow in <10 seconds
- Profile data syncs correctly
- Avatar displays in navigation
- Subsequent logins faster (no re-consent)
- Traditional login still available as fallback

---

## User Flows

### Flow 1: New User Onboarding

**Goal:** Get new user registered, logged in, and rating their first movie within 5 minutes.

**Starting Point:** User visits https://popquiz.rrchnm.org (not logged in)

**Steps:**

1. **Land on Homepage**
   - See welcome message: "Welcome to PopQuiz!"
   - Limited content visible (no ratings, stats hidden)
   - Prominent "Login" and "Sign Up" buttons in navigation

2. **Click "Sign Up" or "Sign in with Slack"**

   **Option A: Traditional Signup**
   - Fill out form: username, email, password
   - No email verification required
   - Click "Sign Up" button
   - Validation: unique username/email, password requirements
   - Error states: username taken, invalid email, password too weak

   **Option B: Slack OAuth**
   - Click "Sign in with Slack" button
   - Redirect to Slack OAuth page
   - Approve permissions (first time only)
   - Redirect back, account auto-created

3. **Account Created & Logged In**
   - Automatic redirect to homepage
   - Now see full content: team members, voting section
   - Navigation shows username and "My Profile" link
   - Welcome message updates: "Welcome, [First Name]!"

4. **Prompted to Start Rating**
   - Prominent "Start Rating Movies" section on homepage
   - Shows: "0 of 658 rated (0%)" with progress bar at 0%
   - Call-to-action button: "Start Rating"

5. **Click "Start Rating"**
   - Navigate to swipe rating interface
   - See first movie card with poster, title, buttons
   - Legend explains rating scale (Loved to Hated + Haven't Seen)
   - Progress bar shows "0 of 658 rated"

6. **Rate First Movie**
   - Click emoji button (e.g., 🙂 Liked)
   - Immediate feedback: next movie loads
   - Progress updates: "1 of 658 rated"
   - Sense of accomplishment + forward momentum

**Success Outcome:**
User successfully registered, logged in, and rated at least one movie within 5 minutes. Understands the interface and feels motivated to continue rating.

**Alternative Paths:**
- User clicks "Login" instead: Goes to login page, enters credentials, same flow from step 3
- User abandons signup: Can browse limited homepage but cannot rate
- Slack OAuth fails: User redirected to signup with error message, can try traditional signup

**Error Paths:**
- Username taken: Inline error, suggest alternatives
- Slack permission denied: Redirect to login with message
- Invalid email: Inline validation error

---

### Flow 2: Rating Movies via Swipe Interface

**Goal:** Rate 20+ movies in a single session efficiently and enjoyably.

**Starting Point:** User is on homepage, logged in

**Steps:**

1. **Navigate to Swipe Interface**
   - Click "Start Rating Movies" button on homepage, OR
   - Click "Movies" in navigation → "Start Rating" button

2. **First Movie Loads**
   - Large poster displayed prominently
   - Movie title and year below poster
   - IMDB link available
   - Five rating buttons in grid (desktop) or row (mobile)
   - "Haven't Seen" button separated visually
   - Progress bar: "47 of 658 rated (7%)"
   - Clear legend shows what each emoji means

3. **Rate Movie (Desktop/Mobile Click)**
   - User reviews poster and title
   - Recalls if they've seen the movie
   - **If seen:** Click appropriate emoji (🤩🙂😐😕😡)
   - **If not seen:** Click ⏭️ Haven't Seen
   - Button press animation (slight scale/color change)

4. **Rate Movie (Mobile Swipe - Alternative)**
   - Touch poster and drag right (>100px) → Loved rating
   - Touch poster and drag left (>100px) → Hated rating
   - Visual feedback: green ✓ overlay (right) or red ✗ overlay (left)
   - Release to confirm rating
   - If swipe <100px: Poster snaps back, no rating saved

5. **AJAX Submission & Next Movie**
   - Rating sent to server (AJAX, <500ms)
   - Server validates and saves rating
   - Server returns next unrated movie data (JSON)
   - UI updates instantly:
     - New movie poster fades in
     - Title/year update
     - Progress bar advances: "48 of 658 rated (8%)"
     - No page reload, seamless transition

6. **Repeat Process**
   - User continues rating movies
   - Progress bar motivates continued engagement
   - Random order keeps content varied
   - Session can be interrupted and resumed (progress persists)

7. **Session Ends**
   - User navigates away when satisfied, OR
   - Completes all movies (rare): "You've rated all 658 movies! 🎉"
   - Can return anytime to rate new movies or update ratings

**Success Outcome:**
User rates 20+ movies in 10-15 minutes, feels accomplished, progress is saved, can see team rankings influenced by their votes.

**Alternative Paths:**
- User rates via category page instead: Same outcome, different UI (grid with inline buttons)
- User wants to change a rating: Navigate to movie detail page or category page, click different emoji
- User isn't sure about rating: Can click "Haven't Seen" to skip for now, will appear again later

**Error Paths:**
- Network failure during submission: Error message, rating not saved, retry button available
- Server error: Error message, can skip to next movie
- All movies rated: Completion message with congratulations, link to view rankings

---

### Flow 3: Adding a New Item

**Goal:** Add a movie or TV show that's not in the database so the team can rate it.

**Starting Point:** User browsing category page, doesn't see a movie they want

**Steps:**

1. **Realize Movie is Missing**
   - User scrolls through movies in category
   - Doesn't find the movie they're looking for
   - Notices "Add Movie" button at top of page

2. **Click "Add Movie"**
   - Navigate to add movie form page
   - See simple form with one input field
   - Instructions: "Enter IMDB URL or ID"
   - Example format shown: `https://www.imdb.com/title/tt0111161/` or `tt0111161`

3. **Find Movie on IMDB (External)**
   - User opens new tab
   - Goes to imdb.com
   - Searches for movie
   - Opens movie page
   - Copies URL from browser address bar

4. **Paste IMDB URL**
   - Return to PopQuiz tab
   - Paste URL into input field
   - URL appears in field: `https://www.imdb.com/title/tt0111161/`
   - Click "Add Movie" button

5. **Submission & Fetching**
   - Loading indicator appears ("Fetching movie data...")
   - Submit button disabled to prevent duplicate clicks
   - Server extracts IMDB ID: tt0111161
   - Server checks if item already exists (duplicate check)
   - If new: Server fetches IMDB page HTML
   - Parser extracts: title, year, director, genre, poster URL
   - Poster image immediately downloaded and cached at `/media/posters/<imdb_id>.jpg`
   - Server creates item record in database with local poster URL
   - Takes 1-5 seconds typically (includes poster download)

6. **Success & Redirect**
   - Success message: "Item added successfully!"
   - Redirected to category page
   - New item appears in grid (at end or based on sort)
   - Item has no ratings yet (all users see it as unrated)
   - Poster loads from local server, not external CDN

7. **Rate the New Item (Optional)**
   - User can immediately rate the item via inline buttons
   - Item now part of team's collection
   - Other users will see it when rating

**Success Outcome:**
Movie successfully added to database with correct metadata, visible to all team members, ready to be rated.

**Alternative Paths:**
- User provides just IMDB ID (tt0111161): Works the same, system handles both formats
- User wants to add multiple movies: Can repeat flow, no limit on additions

**Error Paths:**
- **Invalid URL format:** Error message "Invalid IMDB URL or ID", form stays populated, user can correct
- **Duplicate movie:** Error message "This movie already exists in [Category]", link to existing movie page
- **IMDB page not found:** Error message "Movie not found on IMDB, check the URL", form stays populated
- **Network timeout:** Error message "Failed to fetch movie data, try again", retry button
- **IMDB scraping fails:** Error message "Couldn't read movie data, try again or contact admin"

---

### Flow 4: Comparing Tastes

**Goal:** Discover compatibility with a teammate and find shared favorites or interesting disagreements.

**Starting Point:** User on homepage, curious about taste overlap

**Steps:**

1. **Navigate to Compare Section**
   - Scroll down on homepage
   - See "Compare Tastes" section
   - Two dropdown menus for selecting users
   - List of all team members in each dropdown

2. **Select Two Users**
   - User selects themselves from first dropdown
   - Selects a teammate from second dropdown
   - "Compare" button becomes active

3. **Click "Compare" Button**
   - Navigate to comparison page URL: `/compare/username1/username2/`
   - Page loads with comparison calculations

4. **View Compatibility Score**
   - Top of page shows compatibility percentage
   - Example: "67% Compatible (22 movies in common)"
   - Calculation: Of movies both rated, 67% had same rating type
   - Venn diagram visualizes overlap

5. **Explore Quick Stats**
   - Three stat boxes show:
     - "Both Love" - 8 movies
     - "Both Hate" - 2 movies
     - "Major Disagreements" - 4 movies
   - Click stat box to jump to that section

6. **Browse Movie Sections**
   - **Both Love Section:**
     - Grid of movie posters both users rated Loved (🤩)
     - Shows 8 movies they both adore
     - Click movie to see detail page

   - **Both Hate Section:**
     - Grid of movies both rated Hated (😡)
     - Shows 2 movies they both disliked
     - Can spark conversation about why

   - **Disagreements Section:**
     - Cards showing movies rated oppositely
     - Each card shows:
       - Movie poster
       - User 1 rating: 🤩 (Loved)
       - User 2 rating: 😡 (Hated)
     - Most interesting for discussion

7. **Discover Only-Rated Movies**
   - "Only [User1] Rated" section shows movies User1 saw but User2 hasn't
   - "Only [User2] Rated" shows reverse
   - Recommendations: "You should watch X, teammate loved it!"

8. **Try 3-Way Comparison (Optional)**
   - Return to homepage
   - Select three users from dropdowns
   - View 3-way Venn diagram with 7 regions
   - More complex but fun for finding group consensus

**Success Outcome:**
User discovers shared favorites to discuss, finds disagreements to spark conversation, gets movie recommendations from teammates, understands taste compatibility.

**Alternative Paths:**
- Compare with multiple teammates: Repeat flow with different selections
- View other users' comparisons: Enter URL directly like `/compare/alice/bob/`
- 3-way comparison: Same flow but with third user selected

**Error Paths:**
- Select same user twice: Error message "Please select different users"
- Users with no common movies: Show "No overlap yet" message with encouragement
- Select non-existent user in URL: 404 page

---

## Out of Scope

### Not in Current Version

**Advanced Features (Future Enhancements):**
- **Books/Music:** Different metadata structure, out of scope
- **Custom Categories:** Users can't create own categories, admin-only
- **Private Ratings:** All ratings are public within team, no privacy controls
- **Rating Changes History:** Don't track when ratings changed, only current value
- **Comments on Movies:** No discussion threads, just ratings
- **Recommendation Algorithm:** Basic "team favorites you haven't seen", no ML
- **Notification System:** No alerts for new movies or ratings
- **Exporting Data:** No CSV export or API access
- **Mobile Native Apps:** Web-only, responsive design

**Social Features:**
- **Following Users:** No follow/unfollow mechanism
- **Private Messages:** No inter-user communication
- **Groups/Teams:** Single team per installation, no multi-tenancy
- **Public Profiles:** Profiles visible only to logged-in team members
- **Sharing Outside Team:** No public sharing or social media posting

**Administrative Features:**
- **Bulk Import:** Can't import large lists of movies at once
- **Movie Editing:** Can't edit movie metadata after adding
- **User Management:** No user banning, deletion limited to admin
- **Analytics Dashboard:** No detailed usage statistics for admins
- **Role-Based Access:** All users have equal permissions

### Explicitly Excluded

**Never Planned:**
- **Spoilers/Reviews:** PopQuiz is for ratings only, not reviews or plot discussion
- **Monetization:** No paid tiers, ads, or premium features
- **Third-Party Integrations:** No Slack notifications, Jira, etc. (except Slack OAuth)
- **Real-Time Collaboration:** No live updates when others rate, refresh required
- **Complex Algorithms:** No machine learning, no personalized weights, simple average only

**Technical Limitations:**
- **Offline Mode:** Requires internet connection, no offline rating
- **Browser Support:** Modern browsers only (Chrome, Firefox, Safari, Edge - no IE11)
- **Performance:** Optimized for teams of 3-20 users, 500-1000 movies
- **Scalability:** SQLite suitable for small teams, not enterprise-scale

**Intentional Design Decisions:**
- **No Decimal Ratings:** 5-point scale only, no 1-10 or star ratings
- **No Half-Ratings:** Can't rate 3.5 stars, must choose one of 5 levels
- **No Weighted Votes:** All users' votes count equally, no expert mode
- **No Time-Based Ranking:** Don't favor recent ratings, all equal weight

---

## Open Questions

### Product Questions

**Q: Should we add a "Watched Together" feature to track group viewing?**
- **Context:** Teams might want to remember which movies they watched as a group
- **Options:**
  - Add "watched together" flag to movies with date
  - Separate "group viewing history" feature
  - Out of scope - use external tool
- **Owner:** Product/User feedback
- **Status:** Collecting user interest, not MVP

**Q: How should we handle movie franchises (e.g., Marvel Cinematic Universe)?**
- **Context:** Users might want to see all movies in a series grouped together
- **Options:**
  - Add franchise tagging (manual or IMDB-sourced)
  - Collections feature to group related movies
  - Leave as-is, use genre or search
- **Owner:** Product + Engineering
- **Status:** Researching IMDB's franchise data availability

**Q: Should profiles show rating statistics (average rating given, most rated genre)?**
- **Context:** Additional profile metrics could be interesting but add complexity
- **Options:**
  - Add stats section to profile (avg rating, genre distribution)
  - Keep profiles focused on movie list
  - Add toggle to show/hide stats
- **Owner:** Product + Design
- **Status:** Exploring in design mockups

### Technical Questions

**Q: What happens when IMDB changes their HTML structure?**
- **Context:** Web scraping is fragile, IMDB may change anytime
- **Options:**
  - Build fallback parser for common patterns
  - Add error handling to gracefully degrade
  - Consider OMDB API (requires key, has limits)
  - Manual fallback: let users enter metadata
- **Owner:** Engineering
- **Status:** Current error handling sufficient, monitor for failures

**Q: Should we cache ranking calculations for performance?**
- **Context:** Recalculating on every page load may be slow with many ratings
- **Options:**
  - Cache rankings with invalidation on new ratings
  - Compute on-demand (current approach)
  - Pre-compute daily rankings
- **Owner:** Engineering
- **Status:** Performance acceptable now, revisit if >1000 movies or >50 users

**Q: How do we handle database permissions in deployment?**
- **Context:** SQLite file ownership can cause readonly errors
- **Options:**
  - Document fix in deployment guide (current)
  - Automate permission check on startup
  - Switch to PostgreSQL (overkill for team size)
- **Owner:** Engineering/DevOps
- **Status:** Documented in SPEC.md, acceptable for now

### User Experience Questions

**Q: Should "Haven't Seen" appear in user's rating history?**
- **Context:** Clutters profile with movies not actually watched
- **Options:**
  - Show in separate "Haven't Seen" section on profile
  - Hide from default view, add toggle to show
  - Never show in profile (only in swipe interface)
- **Owner:** Product + Design
- **Status:** Currently shown, gathering user feedback

**Q: How should we handle duplicate/similar movies (remakes, different cuts)?**
- **Context:** The Departed (2006) vs Infernal Affairs (2002), Blade Runner vs Final Cut
- **Options:**
  - Allow both, treat as separate movies
  - Link related movies somehow
  - Admin manually merges/removes duplicates
- **Owner:** Product
- **Status:** Allow both for now, edge case not critical

---

*Last Updated: 2026-02-18*
*This specification is maintained for product planning and feature development.*
