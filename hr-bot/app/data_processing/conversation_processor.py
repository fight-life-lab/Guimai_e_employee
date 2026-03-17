"""Conversation record processor for text files."""

import re
import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


logger = logging.getLogger(__name__)


class ConversationProcessor:
    """Process conversation records from text files."""
    
    def __init__(self):
        """Initialize the conversation processor."""
        # Common patterns for extracting conversation information
        self.date_patterns = [
            r'(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})[日]?',
            r'(\d{1,2})[月/-](\d{1,2})[日]?',
            r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
        ]
        
        self.employee_name_patterns = [
            r'员工[:：]\s*([^\n]+)',
            r'姓名[:：]\s*([^\n]+)',
            r'谈话对象[:：]\s*([^\n]+)',
            r'([^\n]+)的谈心谈话记录',
            r'([^\n]+)的绩效面谈记录',
        ]
        
        self.conversation_type_keywords = {
            '谈心谈话': ['谈心谈话', '日常谈话', '沟通谈话'],
            '绩效面谈': ['绩效面谈', '绩效沟通', '绩效考核'],
            '离职面谈': ['离职面谈', '离职沟通', '离职谈话'],
            '入职面谈': ['入职面谈', '入职沟通', '新员工谈话'],
            '转正面谈': ['转正面谈', '转正沟通', '试用期谈话'],
        }
    
    def process_text_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Process a text file containing conversation records.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            List of conversation record dictionaries
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split content into individual conversation records
            conversations = self._split_conversations(content)
            
            processed_conversations = []
            for conversation in conversations:
                record = self._parse_conversation(conversation)
                if record:
                    processed_conversations.append(record)
            
            logger.info(f"Processed {len(processed_conversations)} conversations from {file_path}")
            return processed_conversations
            
        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {e}")
            return []
    
    def process_markdown_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Process a markdown file containing conversation records.
        
        Args:
            file_path: Path to the markdown file
            
        Returns:
            List of conversation record dictionaries
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove markdown formatting
            content = self._clean_markdown(content)
            
            # Process as text
            return self.process_text_file_content(content, file_path)
            
        except Exception as e:
            logger.error(f"Error processing markdown file {file_path}: {e}")
            return []
    
    def process_text_file_content(self, content: str, source: str = "text") -> List[Dict[str, Any]]:
        """Process text content containing conversation records.
        
        Args:
            content: Text content
            source: Source identifier
            
        Returns:
            List of conversation record dictionaries
        """
        try:
            # Split content into individual conversation records
            conversations = self._split_conversations(content)
            
            processed_conversations = []
            for conversation in conversations:
                record = self._parse_conversation(conversation)
                if record:
                    processed_conversations.append(record)
            
            logger.info(f"Processed {len(processed_conversations)} conversations from {source}")
            return processed_conversations
            
        except Exception as e:
            logger.error(f"Error processing text content from {source}: {e}")
            return []
    
    def _split_conversations(self, content: str) -> List[str]:
        """Split content into individual conversation records.
        
        Args:
            content: Text content
            
        Returns:
            List of conversation text blocks
        """
        # Try different splitting strategies
        
        # Strategy 1: Split by date patterns (most common)
        date_split_pattern = r'\n\s*(?=\d{4}[年/-]|\d{1,2}[月/-])'
        conversations = re.split(date_split_pattern, content)
        
        if len(conversations) > 1:
            return conversations
        
        # Strategy 2: Split by employee name patterns
        name_split_pattern = r'\n\s*(?=员工[:：]|姓名[:：]|谈话对象[:：])'
        conversations = re.split(name_split_pattern, content)
        
        if len(conversations) > 1:
            return conversations
        
        # Strategy 3: Split by double newlines
        conversations = re.split(r'\n\s*\n', content)
        
        return conversations if conversations else [content]
    
    def _parse_conversation(self, conversation_text: str) -> Optional[Dict[str, Any]]:
        """Parse a single conversation text into structured data.
        
        Args:
            conversation_text: Text of a single conversation
            
        Returns:
            Dictionary with conversation data or None if parsing fails
        """
        if not conversation_text.strip():
            return None
        
        try:
            # Extract conversation date
            conversation_date = self._extract_date(conversation_text)
            
            # Extract employee name
            employee_name = self._extract_employee_name(conversation_text)
            
            # Determine conversation type
            conversation_type = self._determine_conversation_type(conversation_text)
            
            # Extract participants
            participants = self._extract_participants(conversation_text)
            
            # Extract summary/content
            content = self._extract_content(conversation_text)
            
            # Extract follow-up actions
            follow_up_actions = self._extract_follow_up_actions(conversation_text)
            
            # Extract next meeting date
            next_meeting_date = self._extract_next_meeting_date(conversation_text)
            
            # Only return if we have at least employee name and date
            if not employee_name or not conversation_date:
                logger.warning(f"Missing essential data (name: {employee_name}, date: {conversation_date}) in conversation")
                return None
            
            return {
                "employee_name": employee_name,
                "conversation_date": conversation_date,
                "conversation_type": conversation_type,
                "participants": participants,
                "content": content,
                "summary": content[:200] + "..." if len(content) > 200 else content,  # Simple summary
                "follow_up_actions": follow_up_actions,
                "next_meeting_date": next_meeting_date,
            }
            
        except Exception as e:
            logger.error(f"Error parsing conversation: {e}")
            return None
    
    def _extract_date(self, text: str) -> Optional[date]:
        """Extract date from conversation text.
        
        Args:
            text: Conversation text
            
        Returns:
            date object or None
        """
        for pattern in self.date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 3:  # Full date with year
                        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                        if year < 100:  # Handle 2-digit years
                            year += 2000 if year < 50 else 1900
                        return date(year, month, day)
                    elif len(groups) == 2:  # Month and day only
                        month, day = int(groups[0]), int(groups[1])
                        current_year = date.today().year
                        return date(current_year, month, day)
                except ValueError:
                    continue
        
        return None
    
    def _extract_employee_name(self, text: str) -> Optional[str]:
        """Extract employee name from conversation text.
        
        Args:
            text: Conversation text
            
        Returns:
            Employee name or None
        """
        for pattern in self.employee_name_patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                # Clean up the name
                name = re.sub(r'[的谈心谈话绩效面谈记录]', '', name)
                return name.strip()
        
        return None
    
    def _determine_conversation_type(self, text: str) -> Optional[str]:
        """Determine conversation type from text content.
        
        Args:
            text: Conversation text
            
        Returns:
            Conversation type or None
        """
        text_lower = text.lower()
        
        for conv_type, keywords in self.conversation_type_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return conv_type
        
        # Default to general conversation if no specific type found
        return "谈心谈话"
    
    def _extract_participants(self, text: str) -> Optional[str]:
        """Extract conversation participants.
        
        Args:
            text: Conversation text
            
        Returns:
            Participants string or None
        """
        # Look for participant mentions
        participant_patterns = [
            r'参与人员[:：]\s*([^\n]+)',
            r'谈话人员[:：]\s*([^\n]+)',
            r'主持人[:：]\s*([^\n]+)',
            r'记录人[:：]\s*([^\n]+)',
        ]
        
        participants = []
        for pattern in participant_patterns:
            matches = re.findall(pattern, text)
            participants.extend(matches)
        
        return "; ".join(participants) if participants else None
    
    def _extract_content(self, text: str) -> str:
        """Extract main conversation content.
        
        Args:
            text: Conversation text
            
        Returns:
            Main content without metadata
        """
        # Remove metadata sections
        content = text
        
        # Remove headers and metadata
        metadata_patterns = [
            r'^[^\n]*员工[:：][^\n]*\n?',
            r'^[^\n]*姓名[:：][^\n]*\n?',
            r'^[^\n]*日期[:：][^\n]*\n?',
            r'^[^\n]*时间[:：][^\n]*\n?',
            r'^[^\n]*参与人员[:：][^\n]*\n?',
            r'^[^\n]*谈话人员[:：][^\n]*\n?',
            r'^[^\n]*主持人[:：][^\n]*\n?',
            r'^[^\n]*记录人[:：][^\n]*\n?',
        ]
        
        for pattern in metadata_patterns:
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
        
        return content.strip()
    
    def _extract_follow_up_actions(self, text: str) -> Optional[str]:
        """Extract follow-up actions from conversation text.
        
        Args:
            text: Conversation text
            
        Returns:
            Follow-up actions or None
        """
        follow_up_patterns = [
            r'后续行动[:：]\s*([^\n]+)',
            r'跟进措施[:：]\s*([^\n]+)',
            r'改进措施[:：]\s*([^\n]+)',
            r'行动计划[:：]\s*([^\n]+)',
            r'下一步[:：]\s*([^\n]+)',
        ]
        
        for pattern in follow_up_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_next_meeting_date(self, text: str) -> Optional[date]:
        """Extract next meeting date from conversation text.
        
        Args:
            text: Conversation text
            
        Returns:
            Next meeting date or None
        """
        next_meeting_patterns = [
            r'下次谈话[:：]\s*' + self.date_patterns[0],
            r'后续跟进[:：]\s*' + self.date_patterns[0],
            r'复查日期[:：]\s*' + self.date_patterns[0],
        ]
        
        for pattern in next_meeting_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) >= 3:
                        year, month, day = int(groups[-3]), int(groups[-2]), int(groups[-1])
                        if year < 100:  # Handle 2-digit years
                            year += 2000 if year < 50 else 1900
                        return date(year, month, day)
                except ValueError:
                    continue
        
        return None
    
    def _clean_markdown(self, text: str) -> str:
        """Clean markdown formatting from text.
        
        Args:
            text: Text with markdown formatting
            
        Returns:
            Cleaned text
        """
        # Remove markdown headers
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        
        # Remove markdown links
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # Remove markdown bold and italic
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)
        
        # Remove markdown code blocks
        text = re.sub(r'```[^\n]*\n([^\n]+)\n```', r'\1', text, flags=re.DOTALL)
        
        return text