# Background Themes Guide

## Available Background Themes

Your DoctorFinder portal now includes 8 beautiful background theme options. Here's how to use them:

### Theme Options

| Theme | Class | Description | Best For |
|-------|-------|-------------|----------|
| Teal (Default) | `bg-theme-teal` | Modern teal gradient | Healthcare, Medical theme |
| Blue | `bg-theme-blue` | Fresh blue gradient | Professional, Tech-savvy |
| Green | `bg-theme-green` | Soft green gradient | Health, Wellness, Growth |
| Orange | `bg-theme-orange` | Warm orange gradient | Friendly, Approachable |
| Purple | `bg-theme-purple` | Premium purple gradient | Luxury, Professional |
| Gray | `bg-theme-gray` | Clean light gray | Minimalist, Corporate |
| Healthcare Blue | `bg-theme-healthcare` | Professional healthcare blue | Medical Practice |
| White | `bg-theme-white` | Clean white background | Minimalist, Modern |

### How to Use

#### Option 1: Set Global Background (Entire Portal)
Edit `app/templates/base.html` and modify the body class:

```html
<!-- Current (Teal theme) -->
<body class="d-flex flex-column bg-theme-teal">

<!-- Change to any other theme by replacing the class -->
<body class="d-flex flex-column bg-theme-blue">
<body class="d-flex flex-column bg-theme-green">
<body class="d-flex flex-column bg-theme-healthcare">
<!-- etc... -->
```

#### Option 2: Set Background Per Page
In individual template files, override the `body_class` block:

```html
{% extends "base.html" %}

{% block body_class %}bg-theme-healthcare{% endblock %}

{% block content %}
    <!-- Your page content -->
{% endblock %}
```

### CSS Customization

To modify or create custom themes, edit `app/static/style.css`:

```css
/* Add a new custom theme */
body.bg-theme-custom {
    background: linear-gradient(135deg, #color1 0%, #color2 50%, #color3 100%);
}
```

### Background Attachment

All themes use `background-attachment: fixed;` which creates a parallax effect - the background stays fixed when scrolling. This adds a professional touch.

### Watermark

The subtle watermark (CareSlotly logo) is very faint (`opacity: 0.03`) and can be:
- Hidden completely by commenting out the `body::after` rule in `style.css`
- Made more visible by increasing the `opacity` value (default 0.03)
- Removed entirely by deleting the `body::after` CSS block

### Tips

1. **Test Different Themes**: Try each theme to see which best matches your brand
2. **Mobile Responsive**: All themes work perfectly on mobile devices
3. **Performance**: Gradients are fast and lightweight
4. **Accessibility**: All themes maintain good contrast with text content

### Current Configuration

**Default Theme**: `bg-theme-teal` (Modern teal gradient)

To change the default, modify `app/templates/base.html` line with the body class.
