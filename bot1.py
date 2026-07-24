from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import sqlite3
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# List of available categories
CATEGORIES = [
    "Personal", "Health", "Entertainment", "Transport", "Food",
    "Housing", "Groceries", "Personal Care", "Phone and Internet",
    "Utilities", "Savings", "Donations", "Shopping", "Travel",
    "Education", "Gifts", "Betting", "Investments", "Loan Repayment"
]

# ============================================
# DATABASE FUNCTIONS
# ============================================

def init_database():
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            description TEXT NOT NULL,
            date TEXT NOT NULL,
            category TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized!")

def add_category_column():
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(expenses)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'category' not in columns:
        cursor.execute('ALTER TABLE expenses ADD COLUMN category TEXT')
        conn.commit()
        print("Category column added to database!")
    
    conn.close()

def save_expense(amount, description, category):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        'INSERT INTO expenses (amount, description, date, category) VALUES (?, ?, ?, ?)',
        (amount, description, now, category)
    )
    
    conn.commit()
    conn.close()

def get_today_expenses():
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute(
        'SELECT id, amount, description, date, category FROM expenses WHERE date LIKE ? ORDER BY date DESC',
        (today + '%',)
    )
    
    expenses = cursor.fetchall()
    
    conn.close()
    return expenses

def delete_expense(expense_id):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
    
    conn.commit()
    conn.close()

def get_most_recent_expense():
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT id, amount, description, date, category FROM expenses ORDER BY date DESC LIMIT 1'
    )
    
    expense = cursor.fetchone()
    
    conn.close()
    return expense

def get_weekly_expenses():
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    cursor.execute(
        'SELECT amount, category FROM expenses WHERE date >= ?',
        (week_ago,)
    )
    
    expenses = cursor.fetchall()
    
    conn.close()
    return expenses

def get_monthly_expenses():
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    
    current_month = datetime.now().strftime('%Y-%m')
    
    cursor.execute(
        'SELECT amount, category FROM expenses WHERE date LIKE ?',
        (current_month + '%',)
    )
    
    expenses = cursor.fetchall()
    
    conn.close()
    return expenses

# ============================================
# CALCULATION & FORMATTING FUNCTIONS
# ============================================

def calculate_category_percentages(expenses):
    """
    Takes a list of (amount, category) tuples.
    Returns a dictionary with category totals and a grand total.
    """
    category_totals = {}
    grand_total = 0
    
    for expense in expenses:
        amount = expense[0]
        category = expense[1] if expense[1] else "Uncategorized"
        
        grand_total += amount
        
        if category in category_totals:
            category_totals[category] += amount
        else:
            category_totals[category] = amount
    
    return {
        'categories': category_totals,
        'grand_total': grand_total
    }

def format_report(title, category_data, grand_total):
    """
    Creates a formatted report string.
    """
    if grand_total == 0:
        return f"{title}\n\nNo expenses in this period!"
    
    message = f"{title}\n\n"
    message += f"💰 Total Spent: ₦{grand_total:.2f}\n\n"
    message += "📊 Breakdown by Category:\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    sorted_categories = sorted(category_data.items(), key=lambda x: x[1], reverse=True)
    
    for category, amount in sorted_categories:
        percentage = (amount / grand_total) * 100
        
        bar_length = int(percentage / 5)
        bar = "▓" * bar_length
        
        message += f"{category}\n"
        message += f"₦{amount:.2f} ({percentage:.1f}%)\n"
        message += f"{bar}\n\n"
    
    return message

# ============================================
# KEYBOARD FUNCTIONS
# ============================================

def create_category_keyboard():
    keyboard = []
    row = []
    
    for i, category in enumerate(CATEGORIES):
        button = InlineKeyboardButton(category, callback_data=f"cat_{category}")
        row.append(button)
        
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    return InlineKeyboardMarkup(keyboard)

async def ask_for_category(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float, description: str):
    context.user_data['pending_amount'] = amount
    context.user_data['pending_description'] = description
    
    keyboard = create_category_keyboard()
    
    await update.message.reply_text(
        f"Great! Now choose a category for:\n"
        f"₦{amount:.2f} - {description}",
        reply_markup=keyboard
    )

# ============================================
# BUTTON CLICK HANDLERS
# ============================================

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("cat_"):
        await handle_category_button(query, context)
    elif query.data.startswith("del_"):
        await handle_delete_button(query, context)
    else:
        await query.edit_message_text("Unknown button clicked.")

async def handle_category_button(query, context):
    if 'pending_amount' not in context.user_data:
        await query.edit_message_text("No pending expense. Please add a new expense.")
        return
    
    amount = context.user_data['pending_amount']
    description = context.user_data['pending_description']
    category = query.data.replace("cat_", "")
    
    save_expense(amount, description, category)
    
    del context.user_data['pending_amount']
    del context.user_data['pending_description']
    
    await query.edit_message_text(
        f"✅ Expense saved!\n"
        f"Amount: ₦{amount:.2f}\n"
        f"Description: {description}\n"
        f"Category: {category}"
    )

async def handle_delete_button(query, context):
    expense_id = int(query.data.replace("del_", ""))
    
    delete_expense(expense_id)
    
    await query.edit_message_text(
        f"✅ Expense deleted!\n\n"
        f"Use /manage to delete more expenses or /today to see remaining expenses."
    )

# ============================================
# COMMAND HANDLERS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to PennySharp Bot! 🎉\n"
        "Your favourite expense tracking bot.\n\n"
        "Type /help to see what I can do."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Here's what I can do:

📝 Basic Commands:
/start - Start the bot and see welcome message
/help - Show this help message

💵 Expense Management:
/today - Show today's expenses
/delete - Delete the most recent expense
/manage - Manage today's expenses (delete specific ones)

📊 Reports:
/weekly - Weekly spending report by category (last 7 days)
/monthly - Monthly spending report by category (current month)

➕ To add an expense:
1. Type: amount description
   Example: 50 coffee
2. Select a category from the buttons
    """
    await update.message.reply_text(help_text)

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expenses = get_today_expenses()
    
    if not expenses:
        await update.message.reply_text("No expenses recorded today. Start adding some!")
        return
    
    message = "📊 Today's Expenses:\n\n"
    total = 0
    
    for expense in expenses:
        expense_id = expense[0]
        amount = expense[1]
        description = expense[2]
        time = expense[3].split()[1]
        category = expense[4] if expense[4] else "Uncategorized"
        
        message += f"• ₦{amount:.2f} - {description}\n"
        message += f"  📁 {category} | ⏰ {time}\n\n"
        
        total += amount
    
    message += f"💰 Total: ₦{total:.2f}"
    
    await update.message.reply_text(message)

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expense = get_most_recent_expense()
    
    if not expense:
        await update.message.reply_text("No expenses to delete!")
        return
    
    expense_id = expense[0]
    amount = expense[1]
    description = expense[2]
    date = expense[3]
    category = expense[4] if expense[4] else "Uncategorized"
    
    delete_expense(expense_id)
    
    await update.message.reply_text(
        f"🗑️ Deleted most recent expense:\n\n"
        f"₦{amount:.2f} - {description}\n"
        f"Category: {category}\n"
        f"Date: {date}"
    )

async def manage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expenses = get_today_expenses()
    
    if not expenses:
        await update.message.reply_text("No expenses to manage today!")
        return
    
    message = "🗂️ Manage Today's Expenses:\n"
    message += "Click the ❌ button to delete an expense\n\n"
    
    keyboard = []
    
    for expense in expenses:
        expense_id = expense[0]
        amount = expense[1]
        description = expense[2]
        time = expense[3].split()[1]
        category = expense[4] if expense[4] else "Uncategorized"
        
        message += f"• ₦{amount:.2f} - {description}\n"
        message += f"  📁 {category} | ⏰ {time}\n"
        
        button = InlineKeyboardButton(
            f"❌ Delete ₦{amount:.2f} - {description[:20]}",
            callback_data=f"del_{expense_id}"
        )
        
        keyboard.append([button])
        
        message += "\n"
    
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expenses = get_weekly_expenses()
    
    result = calculate_category_percentages(expenses)
    category_data = result['categories']
    grand_total = result['grand_total']
    
    report = format_report(
        "📅 Weekly Expense Report (Last 7 Days)",
        category_data,
        grand_total
    )
    
    await update.message.reply_text(report)

async def monthly_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expenses = get_monthly_expenses()
    
    result = calculate_category_percentages(expenses)
    category_data = result['categories']
    grand_total = result['grand_total']
    
    month_name = datetime.now().strftime('%B %Y')
    
    report = format_report(
        f"📅 Monthly Expense Report ({month_name})",
        category_data,
        grand_total
    )
    
    await update.message.reply_text(report)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        await update.message.reply_text(
            "I don't understand. Please use this format:\n"
            "amount description\n\n"
            "Example: 50 coffee"
        )
        return
    
    try:
        amount = float(parts[0])
        description = parts[1]
        
        if amount <= 0:
            await update.message.reply_text("Amount must be greater than 0!")
            return
        
        await ask_for_category(update, context, amount, description)
        
    except ValueError:
        await update.message.reply_text(
            "The amount must be a number!\n\n"
            "Example: 50 coffee"
        )

# ============================================
# MAIN FUNCTION
# ============================================

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get token from environment variable
    TOKEN = os.getenv('BOT_TOKEN')
    
    # Check if token was loaded
    if not TOKEN:
        print("ERROR: BOT_TOKEN not found in .env file!")
        print("Please create a .env file with your bot token.")
        return
    
    init_database()
    add_category_column()
    # ... rest of the code stays the same
    
    app = Application.builder().token(TOKEN).build()
    
    # Register all command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("manage", manage_command))
    app.add_handler(CommandHandler("weekly", weekly_command))
    app.add_handler(CommandHandler("monthly", monthly_command))
    
    # Register button click handler
    app.add_handler(CallbackQueryHandler(handle_button_click))
    
    # Register message handler (must be last)
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()