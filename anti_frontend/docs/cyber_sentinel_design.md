# Design System Specification: High-Tech Editorial

## 1. Overview & Creative North Star

### The Creative North Star: "The Digital Sentinel"
This design system is built to convey absolute authority, data integrity, and futuristic precision. It moves beyond standard "SaaS dashboards" by adopting a **High-End Editorial** approach—treating data intelligence as a premium, curated experience. 

The aesthetic is defined by **Atmospheric Depth**. By leveraging a deep navy and charcoal foundation, we create a "low-light" command center environment. We break the traditional box-model grid through intentional asymmetry, overlapping glass surfaces, and a "Data-Ink" philosophy where every pixel must justify its existence. The result is a UI that feels less like a webpage and more like a sophisticated tactical interface.

---

## 2. Colors & Tonal Architecture

### Color Palette
*   **Background & Surfaces:** Built on `#090e17` (Surface). We utilize a range of `surface-container` tiers to create depth without relying on borders.
*   **Primary Accents:** Vibrant blues (`primary`: `#5cbfff`) and cyans (`tertiary`: `#81ecff`) act as high-visibility beacons for navigation and critical data points.
*   **Semantic Alerts:** Errors are handled with sophisticated warmth (`error`: `#ff716c`), avoiding harsh red tones in favor of a "glowing alert" feel.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning or layout containment. 
*   **Boundary Definition:** Use background color shifts. For example, a `surface-container-low` component should sit on a `surface` background. The slight tonal shift is sufficient to define the edge.
*   **Intentional Asymmetry:** Avoid perfectly centered layouts. Use wide margins and offset containers to create a sense of scanning a wide-field intelligence display.

### The "Glass & Gradient" Rule
To achieve a signature, custom feel, floating elements (modals, popovers, or high-priority cards) must use **Glassmorphism**. 
*   **Formula:** `surface-container-high` at 60% opacity + 20px `backdrop-blur`. 
*   **Gradients:** Use subtle linear gradients for CTAs, transitioning from `primary` (#5cbfff) to `primary-container` (#0cb3ff). This adds a "lithic" glow that feels three-dimensional and powered.

---

## 3. Typography: The Editorial Edge

The system pairs the technical precision of **Inter** with the futuristic, architectural personality of **Space Grotesk**.

*   **Display & Headlines (Space Grotesk):** Used for high-level data summaries and page titles. The wide apertures and geometric forms of Space Grotesk convey a high-tech, "calculated" look.
*   **Body & Labels (Inter):** Reserved for density and readability. Inter's neutral tone ensures that complex data remains legible even at small scales.

**Hierarchy as Identity:**
- **Display-LG (3.5rem):** Used for singular, heroic data points (e.g., Risk Scores).
- **Headline-MD (1.75rem):** Used for section titles.
- **Label-SM (0.6875rem):** Used for metadata, always in All-Caps with +5% letter spacing to mimic "technical readout" aesthetics.

---

## 4. Elevation & Depth

### The Layering Principle
Depth is achieved through **Tonal Layering** rather than traditional structural lines. Imagine the UI as stacked sheets of darkened glass.
*   **Base:** `surface` (#090e17)
*   **Sectioning:** `surface-container-low` (#0e131d)
*   **Active Components:** `surface-container-highest` (#1f2633)

### Ambient Shadows
Shadows should feel like a natural light "glow" rather than a drop shadow.
*   **Specification:** Use a 40px to 64px blur radius with only 4-6% opacity. 
*   **Color:** Use the `primary` or `on-surface` tint for the shadow color to ensure it feels integrated into the environment.

### The "Ghost Border" Fallback
If a border is required for extreme accessibility needs, use a **Ghost Border**:
*   `outline-variant` (#434853) at **15% opacity**. 
*   **Strictly forbidden:** 100% opaque, high-contrast borders.

---

## 5. Components

### Buttons
*   **Primary:** Gradient fill (`primary` to `primary-container`), `md` (0.375rem) roundedness. No border. Text is `on-primary` (#003854) Bold.
*   **Secondary:** Ghost style. Transparent fill with a `primary` Ghost Border (15% opacity).
*   **States:** On hover, primary buttons should increase their "inner glow" (box-shadow: inset 0 0 10px rgba(255,255,255,0.2)).

### Input Fields
*   **Surface:** Use `surface-container-lowest` (#000000).
*   **Focus State:** The field background remains dark, but a 1px "Ghost Border" of `primary` appears at 40% opacity.
*   **Typography:** All user input uses `body-md` in `on-surface`.

### Cards & Data Lists
*   **Constraint:** No horizontal dividers.
*   **Separation:** Use vertical white space and `label-sm` headers to group information. 
*   **Background textures:** Incorporate a subtle "Data-Grid" texture (a 24px dot grid at 3% opacity) within the `surface-container-low` background to reinforce the "high-tech" theme.

### Signature Component: The "Intelligence Badge"
For status indicators (e.g., "Secure", "Analyzing"), use a `tertiary` (#81ecff) glow. The badge should have a background blur and a high-contrast label to make it pop against the dark background.

---

## 6. Do's and Don'ts

### Do
*   **DO** use whitespace as a separator. Give data room to "breathe" like a high-end magazine layout.
*   **DO** use `tertiary` (Cyan) for data highlights and `primary` (Blue) for actions.
*   **DO** apply `backdrop-filter: blur(12px)` to all overlapping navigation elements.
*   **DO** use "Space Grotesk" for numbers and metrics to emphasize their importance.

### Don't
*   **DON'T** use pure white (#FFFFFF) for text. Use `on-surface` (#e1e5f3) to reduce eye strain in dark mode.
*   **DON'T** use default "Material Design" shadows. Keep them soft, wide, and tinted.
*   **DON'T** use 100% opaque borders to separate list items; let the alignment and typography create the rhythm.
*   **DON'T** use bright, saturated backgrounds for large sections. Keep the "The Digital Sentinel" atmosphere dark and moody.