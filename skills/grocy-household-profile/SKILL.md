---
name: grocy-household-profile
description: >
  Personalization context layer for Grocy. Contains storage locations, typical
  products, default expiry settings, and quantity units used by all other Grocy
  skills. Use this skill whenever the user mentions household settings, storage
  preferences, default locations, preferred units, or wants to personalize how
  their Grocy assistant behaves. Also trigger when the user says "update my
  profile", "change my settings", "show my locations", or sets up Grocy for the
  first time. Every other Grocy skill loads this profile for context — if it
  doesn't exist yet, prompt the user to fill it in.
---

# Grocy Household Profile

This skill is a personalization template, not a functional API skill. It provides context that all other Grocy skills reference when making decisions about storage locations, default expiry days, quantity units, and purchasing behavior.

## How This Works

The household profile is a structured YAML block that the user fills in once and updates as needed. When any Grocy skill triggers, it loads this profile to personalize its behavior — choosing the right default location for purchases, estimating expiry dates, and using consistent quantity units.

If the profile doesn't exist yet when another skill needs it, prompt the user to set it up. Walk them through each section conversationally — don't dump the whole template at once.

## Key Profile Concepts

Grocy's household profile structure reflects its product-centric approach:

1. **No household members**: Grocy doesn't track who lives in the household. Focus on storage locations and products.
2. **Location-centric**: Everything revolves around where products are stored (Fridge, Freezer, Pantry).
3. **No keywords**: Grocy doesn't have a tagging/keyword system for recipes. Dietary preferences are tracked as free-text notes.
4. **Product groups**: Grocy organizes products into groups (Dairy, Meat, Vegetables) for categorization.
5. **Quantity unit flexibility**: Grocy has distinct stock/purchase/consume units with conversion factors.

## Profile Template

Help the user fill in this template. Adapt it to their situation — not every field is relevant to every household.

```yaml
# Grocy Household Profile
# Edit this to personalize your Grocy AI assistant.

household_name: "My Home"
language: "en"

# Dietary settings (free-form, no keyword system in Grocy)
dietary_settings:
  vegetarian: false
  vegan: false
  allergies: []          # e.g., ["nuts", "shellfish", "gluten"]
  disliked_ingredients: []  # e.g., ["cilantro", "olives"]

# Where food is stored (must match Grocy Location names)
# Use get_master_data() to discover existing locations
inventory_locations:
  - name: "Refrigerator"
    grocy_location_id: null  # Fill from the get_master_data() locations
    typical_contents: ["Fresh produce", "Dairy", "Leftovers", "Condiments"]
    default_expiry_days: 7
    is_freezer: false
  - name: "Freezer"
    grocy_location_id: null
    typical_contents: ["Frozen vegetables", "Meat", "Ice cream", "Dough"]
    default_expiry_days: 90
    is_freezer: true
  - name: "Pantry"
    grocy_location_id: null
    typical_contents: ["Dry goods", "Canned food", "Rice", "Pasta", "Spices"]
    default_expiry_days: null  # No default expiry for pantry
    is_freezer: false

# Quantity units (must match Grocy QuantityUnit names)
# Use get_master_data() to discover available units
quantity_units:
  default_weight: "g"
  default_volume: "ml"
  default_piece: "Piece"
  common_units:
    - name: "g"
      description: "Grams (weight)"
    - name: "kg"
      description: "Kilograms (weight)"
    - name: "ml"
      description: "Milliliters (volume)"
    - name: "l"
      description: "Liters (volume)"
    - name: "Piece"
      description: "Individual items"
    - name: "Pack"
      description: "Pre-packaged items"

# Product groups (must match Grocy ProductGroup names)
# Use get_master_data() to discover available groups
product_groups:
  - name: "Dairy"
    typical_location: "Refrigerator"
    default_expiry_days: 14
  - name: "Meat"
    typical_location: "Refrigerator"
    default_expiry_days: 3
  - name: "Vegetables"
    typical_location: "Refrigerator"
    default_expiry_days: 7
  - name: "Pantry Items"
    typical_location: "Pantry"
    default_expiry_days: null
  - name: "Frozen"
    typical_location: "Freezer"
    default_expiry_days: 90

# Default shopping and purchase settings
purchase_defaults:
  default_store: ""  # Grocy doesn't have supermarket aisle ordering
  typical_shopping_day: "Saturday"
  default_expiry_buffer_days: 3  # How many days before expiry to flag for use

# Custom rules (free text, referenced by other skills)
custom_rules:
  - "Always prioritize using ingredients that are about to expire"
  - "When in doubt about location, ask the user"
  - "Suggest simple recipes when many items are expiring"
```

## Entity Resolution

Grocy MCP tools that accept names (for example `location_name`, `product_name`, `unit_name`) resolve them to Grocy IDs before calling the API.

Resolution behavior:

1. **Exact match first**: case-insensitive exact names are accepted.
2. **Fuzzy match second**: if no exact match exists, tools may use the closest name above the resolver threshold.
3. **Ambiguity handling**: if multiple close matches exist, tools return an error with suggestions instead of guessing.
4. **Strict resolution for locations**: product creation and product update use strict location resolution, so low-confidence location matches are rejected.

Confidence levels:

- **High**: very likely correct.
- **Medium**: probably correct, but worth checking when the name is important.
- **Low**: may be wrong; prefer an explicit `*_id` field.

Best practice:

- Use `location_id`, `product_id`, and `qu_id_*` when precision is critical.
- Use names for convenience when they are exact and unambiguous.
- If a tool returns `matches`, inspect them before retrying.

Example:

```
Agent: get_master_data()
# Returns locations such as:
# - id=10, name="Gefrierschrank"
# - id=11, name="Vorratsschrank"

Agent: create_product(name="Bulgur", location_name="Vorratsschrank", ...)
```

Because the name is exact, it resolves to `location_id=11`. If the name were misspelled or close to another location, the tool should reject the low-confidence match and ask for the ID.

## Storage

The household profile is stored as the **content of this skill file itself**. The user edits the YAML block above directly in this SKILL.md file, replacing the placeholder values with their actual household details.

When another skill says "Load the grocy-household-profile skill", the agent should read this file and extract the YAML configuration block between the triple-backtick fences. The values in that block are the active profile.

## Discovering Existing Grocy Configuration

When setting up the profile, discover what already exists in the Grocy instance with one call:

```
Tool: get_master_data()
Returns: {
  locations: [{id, name, is_freezer, ...}],
  quantity_units: [{id, name, name_plural, description, ...}],
  product_groups: [{id, name, ...}]
}
```

- Map each location to an entry in `inventory_locations`, filling in `grocy_location_id` with the actual ID.
- Update `quantity_units.common_units` with the actual units available in the instance.
- Update `product_groups` to match the groups configured in Grocy.

## How Other Skills Use This Profile

Each functional skill reads specific sections:

**grocy-inventory-management** reads `inventory_locations` to determine where to store purchases, `quantity_units` for amount parsing, and `dietary_settings` to flag allergens.

**grocy-recipe-discovery** reads `dietary_settings` (allergies, disliked ingredients) to filter results, and `custom_rules` for prioritization logic.

**grocy-shopping-list** reads `quantity_units` for consistent amount formatting and `purchase_defaults` for shopping context.

**grocy-meal-planning** reads `dietary_settings` for filtering and `custom_rules` for planning preferences.

**grocy-product-management** reads `inventory_locations` to suggest default location, `quantity_units` for unit assignment, and `product_groups` for categorization.

**grocy-recipe-import** reads `quantity_units` to match ingredient units and `dietary_settings` to flag recipe conflicts.

## Updating the Profile

When the user wants to change their profile, update only the relevant fields. Common updates include:

- Adding a new storage location (e.g., a second fridge)
- Updating dietary restrictions (new allergy, going vegetarian)
- Adding custom rules for specific preferences

Always confirm changes before applying them — the profile affects how all other skills behave.

## Initial Setup Conversation

When the user first sets up their profile, guide them through it conversationally:

1. **Locations**: "Let me discover your Grocy locations..." → `get_master_data()` → "I found [Refrigerator, Freezer, Pantry]. Does this match your setup?"

2. **Units**: "What units do you typically use for groceries? Grams and milliliters, or pounds and cups?"

3. **Dietary needs**: "Any dietary restrictions or allergies I should know about?"

4. **Product groups**: "Let me check your product groups..." → the `product_groups` from `get_master_data()` → "I see [Dairy, Meat, ...]. Want me to set typical locations for each?"

5. **Custom rules**: "Any special preferences? For example, 'always use up expiring items first' or 'suggest vegetarian options on weekdays'."

After collecting answers, generate the complete YAML block and show it to the user for confirmation.
