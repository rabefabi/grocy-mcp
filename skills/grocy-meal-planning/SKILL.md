---
name: grocy-meal-planning
description: >
  Plan meals in Grocy. Handles creating meal plan entries for specific dates,
  viewing weekly meal plans, and removing planned meals. Use this skill whenever
  the user wants to plan meals for a day or week, asks "what's for dinner this
  week", wants to add a recipe to a specific day, or needs to modify an existing
  meal plan. Also trigger when the user says "plan dinner for Monday", "show me
  this week's plan", "remove Tuesday's lunch", or discusses meal prep. For
  finding recipes to add to the plan, use grocy-recipe-discovery. For shopping
  list generation from the plan, use grocy-shopping-list.
---

# Meal Planning

Help the user plan what to cook and when. Grocy's meal planning is manual — each recipe must be selected individually, and entries use the recipe's base servings.

## Before You Start

Load the **grocy-household-profile** skill for: dietary settings and any custom meal planning rules.

## Grocy Specifics

1. **No auto-plan**: Grocy doesn't have automatic meal planning. The user must select each recipe manually.
2. **No per-entry servings**: Meal plan entries use the recipe's base servings. If the user wants to scale, they need to adjust the recipe or plan multiple entries.
3. **Meal types**: Grocy uses `type` (not `meal_type`) to categorize meals (breakfast, lunch, dinner, etc.).

## Available MCP Tools

### Meal Plan Queries

- `get_meal_plan(from_date=..., to_date=...)` — get meal plan entries for a date range. Returns recipes, dates, and types.

### Meal Plan Operations

- `create_meal_plan_entry(recipe_id=..., recipe_name=..., date=..., type=...)` — add a recipe to the meal plan. Date format: "YYYY-MM-DD". Type is optional (e.g., "breakfast", "lunch", "dinner").
- `delete_meal_plan_entry(entry_id=...)` — remove a meal plan entry. **Get entry_id from `get_meal_plan()` response.**

## Workflow: View Meal Plan

```
User: "What's for dinner this week?"
Agent: get_meal_plan(from_date="2024-04-15", to_date="2024-04-21")
```

### Response Format

```
📅 Meal Plan: April 15-21

Monday (Apr 15):
  🍳 Breakfast: -
  🥗 Lunch: Caesar Salad
  🍝 Dinner: Pasta Carbonara

Tuesday (Apr 16):
  🍳 Breakfast: -
  🥗 Lunch: Leftover pasta
  🍝 Dinner: Chicken Stir Fry

Wednesday (Apr 17):
  [empty - no meals planned]
  
...
```

For empty days, offer suggestions: "Wednesday has no meals planned. Want me to suggest something based on your current stock?"

## Workflow: Plan a Meal

### Single Meal

```
User: "Plan Pasta Carbonara for Monday dinner"
Agent: create_meal_plan_entry(recipe_name="Pasta Carbonara", date="2024-04-15", type="dinner")
```

### Multiple Meals

```
User: "Plan dinner for the whole week"
Agent: 
  1. Get suggestions from grocy-recipe-discovery (check fulfillment)
  2. Present options for each day
  3. Create entries as user confirms
```

### Without Specifying Meal Type

```
User: "Add Pasta Carbonara to Monday"
Agent: "Which meal? Breakfast, lunch, or dinner?"
User: "Dinner"
Agent: create_meal_plan_entry(recipe_name="Pasta Carbonara", date="2024-04-15", type="dinner")
```

## Workflow: Modify Plan

### Remove a Meal

```
User: "Remove Tuesday's dinner"
Agent:
  1. get_meal_plan(from_date="2024-04-16", to_date="2024-04-16")
  2. Find dinner entry, get entry_id
  3. "I found 'Chicken Stir Fry' planned for Tuesday dinner. Remove it?"
  4. User confirms
  5. delete_meal_plan_entry(entry_id=123)
```

### Swap Meals

```
User: "Move Monday's dinner to Wednesday"
Agent:
  1. Get Monday's dinner entry
  2. Delete it: delete_meal_plan_entry(entry_id=...)
  3. Create new entry: create_meal_plan_entry(..., date="Wednesday")
```

### Reschedule

Grocy doesn't have an "update" endpoint for meal plans. To reschedule:
1. Delete the old entry
2. Create a new entry with the new date

## Servings Limitation

**Grocy 4.6+ does not support per-entry servings in meal plans.** Each entry uses the recipe's base servings.

If the user asks to plan for different servings:
1. Acknowledge the limitation: "Grocy meal plans use each recipe's base servings."
2. Suggest alternatives:
   - "You could plan the recipe twice for double portions."
   - "You could adjust the recipe's base servings in Grocy."
   - "I'll note the desired servings, but the actual calculation uses the recipe default."

## Suggested Workflow: Weekly Planning

A typical weekly planning session:

1. **Start**: "Let's plan meals for next week (April 15-21)"
2. **Check calendar**: Ask about any special days (guests, events)
3. **Check inventory**: Use grocy-recipe-discovery to find recipes with ingredients in stock
4. **Day by day**:
   - "For Monday dinner, I suggest Pasta Carbonara (all ingredients in stock). Or would you prefer something else?"
   - User confirms or picks alternative
   - `create_meal_plan_entry(...)`
5. **Review**: Show the complete week's plan
6. **Shopping list**: "Want me to add missing ingredients to your shopping list?"

## Common Query Patterns

| User request | Tool sequence |
|--------------|---------------|
| "What's for dinner?" | `get_meal_plan(from_date=today, to_date=today)` |
| "Show this week's plan" | `get_meal_plan(from_date=..., to_date=...)` |
| "Plan dinner for Monday" | `create_meal_plan_entry(date="Monday", type="dinner", ...)` |
| "Remove Tuesday lunch" | Find entry → `delete_meal_plan_entry(entry_id=...)` |
| "Plan meals for the week" | Interactive workflow: suggest → confirm → create |

## Date Handling

- Accept natural language: "Monday", "tomorrow", "next week"
- Convert to YYYY-MM-DD format for API calls
- Always confirm dates with user: "Planning for Monday, April 15th. Correct?"

### Week Boundaries

When user says "this week" or "next week":
- Assume Monday-Sunday week (or localized)
- Confirm the date range before proceeding

## Error Handling

### Recipe Not Found

```json
{
  "error": "Recipe not found",
  "matches": ["Pasta Carbonara", "Pasta Primavera"],
  "suggestion": "Did you mean one of these?"
}
```

Present options and let user choose.

### Invalid Date

If the date can't be parsed, ask for clarification:
"I couldn't understand the date. Could you specify it as 'April 15' or 'next Monday'?"

### Entry Not Found for Deletion

If `delete_meal_plan_entry()` fails:
"I couldn't find that meal plan entry. Let me check what's planned..." → `get_meal_plan()`

## Integration with Other Skills

- **grocy-recipe-discovery**: Find recipes to add to the plan
- **grocy-shopping-list**: Generate shopping list from planned recipes
- **grocy-inventory-management**: Check what's in stock for planning decisions
- **grocy-household-profile**: Consider dietary preferences when suggesting

## Example: Full Week Planning

```
User: "Help me plan dinner for next week"

Agent: "Let's plan dinners for April 15-21. I'll check what you have in stock..."

[calls get_recipes_fulfillment()]

Agent: "Here are some recipes you can make with current ingredients:
1. Pasta Carbonara (4 servings) ✅
2. Vegetable Stir Fry (2 servings) ✅
3. Cheese Omelette (1 serving) ✅

And some that need 1-2 items:
4. Chicken Curry (need: coconut milk)
5. Fish Tacos (need: tortillas, lime)

For Monday, how about Pasta Carbonara?"

User: "Sure"

Agent: [creates entry] "Done! Pasta Carbonara for Monday dinner.

For Tuesday?"

[continues through the week...]

Agent: "Here's your week:
- Mon: Pasta Carbonara
- Tue: Vegetable Stir Fry
- Wed: Chicken Curry
- Thu: Fish Tacos
- Fri: Cheese Omelette (quick Friday!)
- Sat: [user's choice]
- Sun: [user's choice]

Should I add the missing ingredients (coconut milk, tortillas, lime) to your shopping list?"
```
