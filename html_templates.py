"""
מודול לניהול תבניות HTML
HTML Template Manager Module
"""

from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class TemplateManager:
    """מנהל תבניות HTML"""
    
    def __init__(self, templates_dir: str = "templates"):
        """
        אתחול מנהל התבניות
        
        Args:
            templates_dir: תיקיית התבניות
        """
        self.templates_dir = Path(__file__).parent / templates_dir
        self.cache = {}
        logger.info(f"TemplateManager initialized with dir: {self.templates_dir}")
    
    def load_template(self, template_name: str) -> str:
        """
        טעינת תבנית HTML
        
        Args:
            template_name: שם הקובץ (עם או בלי .html)
        
        Returns:
            תוכן התבנית כ-string
        """
        # הוסף .html אם חסר
        if not template_name.endswith('.html'):
            template_name += '.html'
        
        # בדוק cache
        if template_name in self.cache:
            return self.cache[template_name]
        
        # טען מקובץ
        template_path = self.templates_dir / template_name
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.cache[template_name] = content
                logger.debug(f"Template loaded: {template_name}")
                return content
        except FileNotFoundError:
            logger.error(f"Template not found: {template_name}")
            return f"<!-- Template {template_name} not found -->"
    
    def render(self, template_name: str, **kwargs) -> str:
        """
        רינדור תבנית עם משתנים
        
        Args:
            template_name: שם התבנית
            **kwargs: משתנים להחלפה
        
        Returns:
            HTML מעובד
        """
        template = self.load_template(template_name)
        
        # החלף משתנים
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            template = template.replace(placeholder, str(value))
        
        return template
    
    def clear_cache(self):
        """ניקוי cache"""
        self.cache.clear()
        logger.info("Template cache cleared")


# Components מוכנים
class ShiftComponents:
    """רכיבי משמרת מוכנים לשימוש"""
    
    def __init__(self, template_manager: TemplateManager):
        self.tm = template_manager
    
    def day_header(self, day_name: str, date: str) -> str:
        """כותרת יום"""
        return self.tm.render('day_header', day_name=day_name, date=date)
    
    def shift_card(
        self,
        shift_type: str,
        shift_category: str,
        station: str,
        status_html: str,
        is_atan: bool = False
    ) -> str:
        """כרטיס משמרת"""
        atan_class = 'atan' if is_atan else ''
        return self.tm.render(
            'shift_card',
            shift_type=shift_type,
            shift_category=shift_category,
            station=station,
            status_html=status_html,
            atan_class=atan_class
        )
    
    def status_assigned(self, employee_name: str) -> str:
        """סטטוס משובץ"""
        return f'''
        <div class="shift-status status-assigned">
            <span>👤</span>
            <span>{employee_name}</span>
        </div>
        '''
    
    def status_empty(self) -> str:
        """סטטוס חסר"""
        return '''
        <div class="shift-status status-empty">
            <span>⚠️</span>
            <span>חסר שיבוץ</span>
        </div>
        '''
    
    def status_cancelled(self) -> str:
        """סטטוס מבוטל"""
        return '''
        <div class="shift-status status-cancelled">
            <span>🚫</span>
            <span>משמרת מבוטלת</span>
        </div>
        '''


# דוגמת שימוש
if __name__ == "__main__":
    # יצירת מנהל תבניות
    tm = TemplateManager()
    
    # יצירת components
    components = ShiftComponents(tm)
    
    # דוגמה 1: כותרת יום
    header = components.day_header("ראשון", "15/02/2026")
    print(header)
    
    # דוגמה 2: כרטיס משמרת
    status = components.status_assigned("יוסי כהן")
    card = components.shift_card(
        shift_type="בוקר",
        shift_category="רגיל",
        station="תחנה א",
        status_html=status,
        is_atan=False
    )
    print(card)
    
    # דוגמה 3: משמרת אטן ריקה
    status = components.status_empty()
    card = components.shift_card(
        shift_type="ערב",
        shift_category="אטן",
        station="תחנה ב",
        status_html=status,
        is_atan=True
    )
    print(card)
